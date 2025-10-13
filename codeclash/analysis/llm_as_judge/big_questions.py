#!/usr/bin/env python3
import argparse
import json
import random
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Literal

import jinja2
import yaml
from minisweagent.models import GLOBAL_MODEL_STATS, get_model
from pydantic import BaseModel
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from typing_extensions import Any

from codeclash.analysis.llm_as_judge.utils import FileLock, Instance, InstanceBatch, get_instances
from codeclash.utils.log import get_logger

logger = get_logger("BigQuestionsEvaluator", emoji="🤖")

config_path = Path(__file__).parent / "big_questions.yaml"


class BigQuestionsModelResponseSchema(BaseModel):
    """Schema for structured output of the model."""

    edit_category: Literal["tweak", "fix", "feature", "change", "none"]
    edits_motivated_by_logs: bool
    edits_motivated_by_insights: bool
    edits_motivated_by_old_static_messages: bool
    edits_reverted_based_on_insights: bool
    edits_tested_with_simulations: bool
    edits_validated_with_unittests: bool
    improved_test_analysis_framework: bool
    reasoning: str

    def pretty_print(self) -> None:
        console = Console()

        table = Table()
        table.add_column("Question", style="cyan", width=40)
        table.add_column("Answer", style="green")

        for field_name, value in self.model_dump().items():
            if field_name == "reasoning":
                continue
            display_name = field_name.replace("_", " ").title()
            if value is True:
                value = "[bold green]✓ Yes[/bold green]"
            elif value is False:
                value = "[bold red]✗ No[/bold red]"
            else:
                value = str(value)
            table.add_row(display_name, str(value))

        reasoning_md = Markdown(self.reasoning)
        content = Group(table, reasoning_md)
        console.print()
        console.print(Panel(content, title="[bold blue]Evaluation Results[/bold blue]", border_style="blue"))
        console.print()


class ModelConfig(BaseModel):
    model_name: str
    model_class: str | None = None
    model_kwargs: dict[str, Any]


class BigQuestionsConfig(BaseModel):
    version: int
    system_prompt: str
    instance_prompt: str
    model: ModelConfig


class BigQuestionsData(BaseModel):
    instance: Instance
    big_questions: BigQuestionsModelResponseSchema
    config_version: int


def extract_triple_backticks(text: str) -> str:
    actions = re.findall(r"```bash\s*\n(.*?)\n```", text, re.DOTALL)
    return actions[0] if actions else ""


class BigQuestions:
    def __init__(self, config: BigQuestionsConfig):
        self.config = config
        self.model = get_model(config.model.model_name, config={"model_kwargs": config.model.model_kwargs, "model_class": config.model.model_class})

    @property
    def data_id(self) -> str:
        return f"big_questions_v{self.config.version}"

    def evaluate(self, instance: Instance) -> None:
        target_path = instance.trajectory_path.parent.parent.parent / "llm_as_judge.json"

        if self._should_skip(target_path, instance):
            logger.info(
                f"Skipping instance {instance.instance_id} because it already exists in {target_path} under key {self.data_id}"
            )
            return

        response = self.model.query(
            messages=self._get_messages(instance), response_format=BigQuestionsModelResponseSchema
        )
        response_data = BigQuestionsModelResponseSchema.model_validate_json(response["content"])
        response_data.pretty_print()
        response_data_json = {
            "result": BigQuestionsModelResponseSchema.model_validate_json(response["content"]).model_dump(mode="json"),
            "instance": instance.model_dump(mode="json"),
        }

        self._save_response(target_path, response_data_json, instance)
        logger.info(f"Evaluated instance {instance.instance_id}. Saved to {target_path} with key {self.data_id}")

    def _format_traj_str(self, messages: list[dict[str, Any]]) -> str:
        trajectory_message_str = ""
        for message in messages:
            content = message["content"]
            if isinstance(message["content"], list):
                assert len(message["content"]) == 1
                content = message["content"][0]["text"]
            if message["role"] == "assistant":
                trajectory_message_str += "\n<action>\n" + extract_triple_backticks(content) + "\n</action>\n"
            elif message["role"] == "user":
                trajectory_message_str += content  # already enclosed in <output>
        return trajectory_message_str

    def _get_messages(self, instance: Instance) -> list[dict[str, Any]]:
        trajectory_messages = json.loads(instance.trajectory_path.read_text())["messages"]
        system_message = self.config.system_prompt
        instance_message = jinja2.Template(self.config.instance_prompt).render(
            trajectory_message_str=self._format_traj_str(trajectory_messages)
        )
        # print(instance_message)
        return [
            {"role": "system", "content": system_message},
            {"role": "user", "content": instance_message},
        ]

    def _should_skip(self, target_path: Path, instance: Instance) -> bool:
        if not target_path.exists():
            logger.debug(f"Not skipping: {target_path} does not exist")
            return False
        content = target_path.read_text()
        if not content.strip():
            logger.debug(f"Not skipping: {target_path} is empty")
            return False
        data = json.loads(content)
        if self.data_id not in data:
            logger.debug(f"Not skipping: {self.data_id} not in {target_path}")
            return False
        if instance.instance_id not in data[self.data_id]:
            logger.debug(f"Not skipping: {instance.instance_id} not in {target_path} under key {self.data_id}")
            return False
        return True

    def _save_response(self, target_path: Path, response_data: dict[str, Any], instance: Instance) -> None:
        # atomic write with file lock in case other analyses are also writing
        with FileLock(target_path.with_suffix(".lock")):
            # read again if changed in the meantime
            data = {}
            if target_path.exists():
                content = target_path.read_text()
                if content.strip():
                    data = json.loads(content)
            data.setdefault(self.data_id, {})[instance.instance_id] = response_data
            target_path.write_text(json.dumps(data))

    def evaluate_bulk(self, instances: list[Instance], *, n_workers: int = 1) -> None:
        """Evaluate multiple instances with optional parallel processing.

        Args:
            instances: List of instances to evaluate
            n_workers: Number of parallel workers (default: 1 for sequential)
        """
        total = len(instances)
        logger.info(f"Starting bulk evaluation of {total} instances with {n_workers} workers")

        if n_workers == 1:
            for i, instance in enumerate(instances, 1):
                logger.info(
                    f"Processing instance {i}/{total}: {instance.instance_id} | Cost: ${GLOBAL_MODEL_STATS.cost:.2f}"
                )
                self.evaluate(instance)
        else:
            completed = 0
            with ThreadPoolExecutor(max_workers=n_workers) as executor:
                future_to_instance = {executor.submit(self.evaluate, instance): instance for instance in instances}

                for future in as_completed(future_to_instance):
                    instance = future_to_instance[future]
                    completed += 1
                    try:
                        future.result()
                        logger.info(
                            f"Completed {completed}/{total}: {instance.instance_id} | Cost: ${GLOBAL_MODEL_STATS.cost:.2f}"
                        )
                    except Exception:
                        logger.error(
                            f"Failed {completed}/{total}: {instance.instance_id} | Cost: ${GLOBAL_MODEL_STATS.cost:.2f}",
                            exc_info=True,
                        )


def load_instances_from_path(path: Path) -> list[Instance]:
    if path.is_file() and path.suffix == ".json":
        logger.info(f"Loading instances from batch file: {path}")
        batch = InstanceBatch.model_validate_json(path.read_text())
        return batch.instances
    logger.info(f"Loading instances from directory: {path}")
    return get_instances(path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "input_dir", type=Path, nargs="+", help="Path to the input dir(s) or to instance batch json files"
    )
    parser.add_argument("--shuffle", action="store_true", help="Shuffle instances before processing")
    parser.add_argument("-n", "--n-workers", type=int, default=1, help="Number of parallel workers (default: 1)")
    args = parser.parse_args()

    config = BigQuestionsConfig.model_validate(yaml.safe_load(config_path.read_text()))
    instances = []
    for input_path in args.input_dir:
        instances.extend(load_instances_from_path(input_path))
    big_questions = BigQuestions(config)
    if args.shuffle:
        random.shuffle(instances)
    big_questions.evaluate_bulk(instances, n_workers=args.n_workers)
