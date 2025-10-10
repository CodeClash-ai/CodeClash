#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path
from typing import Literal

import jinja2
import yaml
from minisweagent.models import GLOBAL_MODEL_STATS, get_model
from pydantic import BaseModel
from typing_extensions import Any

from codeclash.analysis.llm_as_judge.utils import FileLock, Instance, get_instances
from codeclash.utils.log import get_logger

logger = get_logger("BigQuestionsEvaluator", emoji="🤖")

config_path = Path(__file__).parent / "big_questions.yaml"


class BigQuestionsModelResponseSchema(BaseModel):
    are_edits_motivated_by_logs: bool
    are_edits_motivated: bool
    are_edits_tested_with_simulations: bool
    are_edits_validated_with_unittests: bool
    edit_category: Literal["tweak", "fix", "feature", "change", "none"]
    reasoning: str


class ModelConfig(BaseModel):
    model_name: str
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


def evaluate(instance: Instance, config: BigQuestionsConfig) -> None:
    target_path = instance.trajectory_path.parent.parent.parent / "llm_as_judge.json"
    data_id = f"big_questions_v{config.version}_{config.model.model_name}_{instance.instance_id}"
    if target_path.exists():
        content = target_path.read_text()
        if content.strip():
            data = json.loads(content)
            if data.get("data_id") == data_id:
                logger.info(
                    f"Skipping instance {instance.instance_id} because it already exists in {target_path} with key {data_id}"
                )
                return
    model = get_model(config.model.model_name, config={"model_kwargs": config.model.model_kwargs})
    trajectory_messages = json.loads(instance.trajectory_path.read_text())["messages"]
    system_message = config.system_prompt
    trajectory_message_str = ""
    for message in trajectory_messages:
        content = message["content"]
        if isinstance(message["content"], list):
            assert len(message["content"]) == 1
            content = message["content"][0]["text"]
        if message["role"] == "assistant":
            trajectory_message_str += "\n<action>\n" + extract_triple_backticks(content) + "\n</action>\n"
        elif message["role"] == "user":
            trajectory_message_str += content  # already enclosed in <output>
    instance_message = jinja2.Template(config.instance_prompt).render(trajectory_message_str=trajectory_message_str)
    # print(instance_message)
    response = model.query(
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": instance_message},
        ],
        response_format=BigQuestionsModelResponseSchema,
    )
    # atomic write with file lock in case other analyses are also writing
    response_data = BigQuestionsModelResponseSchema.model_validate_json(response["content"]).model_dump()
    with FileLock(target_path):
        # read again if changed in the meantime
        data = {}
        if target_path.exists():
            content = target_path.read_text()
            if content.strip():
                data = json.loads(content)
        data[data_id] = response_data
        target_path.write_text(json.dumps(data))
    logger.info(
        f"Evaluated instance {instance.instance_id}: {response_data}. Saved to {target_path} with key {data_id}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path, help="Path to the input dir")
    args = parser.parse_args()

    config = BigQuestionsConfig.model_validate(yaml.safe_load(config_path.read_text()))
    instances = get_instances(args.input_dir)
    for instance in instances:
        evaluate(instance, config)
        print(GLOBAL_MODEL_STATS.cost)
