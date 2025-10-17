#!/usr/bin/env python3
import argparse
import random
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

from codeclash.analysis.llm_as_judge.big_questions import (
    BigQuestions,
    ModelConfig,
    PortkeyWithStructuredOutput,
    load_instances_from_path,
)
from codeclash.analysis.llm_as_judge.utils import Instance
from codeclash.utils.log import get_logger

logger = get_logger("HallucinationEvaluator", emoji="🔍")

config_path = Path(__file__).parent / "hallucination.yaml"


categories = [
    "misinterpretation.log",
    "misinterpretation.log.loss_reason",
    "misinterpretation.sourcecode",
    "misinterpretation.sourcecode.loss_reason",
    "misinterpretation.execution_output.test",
    "misinterpretation.execution_output.test.loss_reason",
    "misinterpretation.execution_output.analysis",
    "misinterpretation.execution_output.analysis.loss_reason",
    "ungrounded_thought",
    "ungrounded_thought.loss_reason",
]


class Incident(BaseModel):
    step_index: int
    incident_category: Literal[*categories]
    detailed_reasoning: str


class HallucinationResponseSchema(BaseModel):
    items: list[Incident]

    def pretty_print(self) -> None:
        console = Console()
        table = Table()
        table.add_column("Step Index", style="cyan", width=10)
        table.add_column("Incident Category", style="green", width=30)
        table.add_column("Detailed Reasoning", style="yellow")
        for item in self.items:
            table.add_row(str(item.step_index), item.incident_category, item.detailed_reasoning)
        console.print(table)


class HallucinationConfig(BaseModel):
    version: int
    system_prompt: str
    instance_prompt: str
    model: ModelConfig


class HallucinationData(BaseModel):
    instance: Instance
    hallucination: HallucinationResponseSchema
    config_version: int


class Hallucination(BigQuestions):
    def __init__(self, config: HallucinationConfig):
        self.config = config
        self.model = PortkeyWithStructuredOutput(
            model_name=config.model.model_name,
            model_kwargs=config.model.model_kwargs,
        )

    @property
    def data_id(self) -> str:
        return f"hallucination_v{self.config.version}"

    def evaluate(self, instance: Instance) -> None:
        target_path = instance.trajectory_path.parent.parent.parent / "llm_as_judge.json"

        if self._should_skip(target_path, instance):
            logger.info(
                f"Skipping instance {instance.instance_id} because it already exists in {target_path} under key {self.data_id}"
            )
            return

        response = self.model.query(messages=self._get_messages(instance), response_format=HallucinationResponseSchema)
        response_data = HallucinationResponseSchema.model_validate_json(response["content"])
        response_data.pretty_print()
        response_data_json = {
            "result": HallucinationResponseSchema.model_validate_json(response["content"]).model_dump(mode="json"),
            "instance": instance.model_dump(mode="json"),
        }

        self._save_response(target_path, response_data_json, instance)
        logger.info(f"Evaluated instance {instance.instance_id}. Saved to {target_path} with key {self.data_id}")

    def _format_traj_str(self, messages: list[dict[str, Any]]) -> str:
        """Format trajectory with step numbers and full agent output (not just actions)."""
        trajectory_message_str = ""
        step_index = 0
        for message in messages:
            content = message["content"]
            if isinstance(message["content"], list):
                assert len(message["content"]) == 1
                content = message["content"][0]["text"]
            if message["role"] == "assistant":
                trajectory_message_str += f'\n<step index="{step_index}">\n{content}\n</step>\n'
                step_index += 1
            elif message["role"] == "user":
                trajectory_message_str += content  # already enclosed in <output>
        return trajectory_message_str


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "input_dir", type=Path, nargs="+", help="Path to the input dir(s) or to instance batch json files"
    )
    parser.add_argument("--shuffle", action="store_true", help="Shuffle instances before processing")
    parser.add_argument("-n", "--n-workers", type=int, default=1, help="Number of parallel workers (default: 1)")
    args = parser.parse_args()

    config = HallucinationConfig.model_validate(yaml.safe_load(config_path.read_text()))
    instances = []
    for input_path in args.input_dir:
        instances.extend(load_instances_from_path(input_path))
    hallucination = Hallucination(config)
    if args.shuffle:
        random.shuffle(instances)
    hallucination.evaluate_bulk(instances, n_workers=args.n_workers)
