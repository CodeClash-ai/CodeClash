#!/usr/bin/env python3
import argparse
import random
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

from codeclash.analysis.llm_as_judge.big_questions import BigQuestions
from codeclash.analysis.llm_as_judge.utils import Instance, InstanceBatch, get_instances
from codeclash.utils.log import get_logger

logger = get_logger("ActionCategorizer", emoji="🏷️")

config_path = Path(__file__).parent / "categorize_actions.yaml"

# Base categories
_read_subcategories = ["source", "logs", "docs", "other"]
_read_subsubcategories = ["new", "old"]

_write_subcategories = [
    "docs",
    "source.main",
    "source.main.backup",
    "source.opponent",
    "source.analysis",
    "source.tests",
    "other",
]
_write_subsubcategories = ["create", "modify_old", "modify_new"]

_execute_subcategories = ["game", "game.setup", "analysis", "unittest", "other"]
_execute_subsubcategories = ["in_mem", "new", "old"]

# Generate all category combinations
_all_categories = (
    ["search", "submit", "other"]
    + [f"read.{sub}.{subsub}" for sub in _read_subcategories for subsub in _read_subsubcategories]
    + [f"write.{sub}.{subsub}" for sub in _write_subcategories for subsub in _write_subsubcategories]
    + [f"execute.{sub}.{subsub}" for sub in _execute_subcategories for subsub in _execute_subsubcategories]
)


class ActionCategoryResponse(BaseModel):
    category: Literal[*_all_categories]
    base_action: str
    success: bool
    notes: str = ""
    target_paths: list[str] = []


class ActionCategoriesModelResponse(BaseModel):
    categories: list[ActionCategoryResponse]

    def pretty_print(self) -> None:
        console = Console()

        table = Table()
        table.add_column("#", style="dim", width=4)
        table.add_column("Category", style="cyan", width=35)
        table.add_column("Base Action", style="green", width=20)
        table.add_column("Target Path", style="green", width=20)
        table.add_column("Success", style="green", width=10)
        table.add_column("Notes", style="yellow")

        for i, action in enumerate(self.categories, 1):
            success_str = "✓" if action.success else "✗"
            table.add_row(
                str(i),
                action.category,
                action.base_action,
                ", ".join(action.target_paths),
                success_str,
                action.notes or "-",
            )

        console.print()
        console.print(table)
        console.print()


class ModelConfig(BaseModel):
    model_name: str
    model_class: str | None = None
    model_kwargs: dict[str, Any] = {}


class ActionCategoriesConfig(BaseModel):
    version: int
    system_prompt: str
    instance_prompt: str = "Categorize the following actions:\n\n{{ trajectory_message_str }}"
    model: ModelConfig


class ActionCategorizer(BigQuestions):
    def __init__(self, config: ActionCategoriesConfig):
        super().__init__(config)

    @property
    def data_id(self) -> str:
        return f"action_categories_v{self.config.version}"

    def evaluate(self, instance: Instance) -> None:
        target_path = instance.trajectory_path.parent.parent.parent / "llm_as_judge.json"

        if self._should_skip(target_path, instance):
            logger.info(
                f"Skipping instance {instance.instance_id} because it already exists in {target_path} under key {self.data_id}"
            )
            return

        response = self.model.query(
            messages=self._get_messages(instance), response_format=ActionCategoriesModelResponse
        )
        response_data = ActionCategoriesModelResponse.model_validate_json(response["content"])
        response_data.pretty_print()
        response_data_json = {
            "result": response_data.model_dump(mode="json"),
            "instance": instance.model_dump(mode="json"),
        }

        self._save_response(target_path, response_data_json, instance)
        logger.info(f"Evaluated instance {instance.instance_id}. Saved to {target_path} with key {self.data_id}")


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

    config = ActionCategoriesConfig.model_validate(yaml.safe_load(config_path.read_text()))
    instances = []
    for input_path in args.input_dir:
        instances.extend(load_instances_from_path(input_path))
    categorizer = ActionCategorizer(config)
    if args.shuffle:
        random.shuffle(instances)
    categorizer.evaluate_bulk(instances, n_workers=args.n_workers)
