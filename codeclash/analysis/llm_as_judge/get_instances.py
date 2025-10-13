#!/usr/bin/env python3

"""Get instances based on specific pattern."""

import argparse
from pathlib import Path

from codeclash.analysis.llm_as_judge.utils import InstanceBatch, get_instances

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path, help="Path to the input log dir")
    parser.add_argument("-o", "--output-file", type=Path, help="Path to the output file", default="instances.json")
    args = parser.parse_args()

    SELECTED_ROUNDS = [1, 5, 10, 15]
    SELECTED_GAME = "BattleSnake"

    # first get all instances, then filter
    instances = sorted(get_instances(args.input_dir), key=lambda x: x.instance_id)
    print(f"Found {len(instances)} instances")
    instances = [instance for instance in instances if SELECTED_GAME in instance.tournament_name]
    print(f"Filtered to {len(instances)} instances because of game name")
    instances = [instance for instance in instances if instance.round_number in SELECTED_ROUNDS]
    print(f"Filtered to {len(instances)} instances because of round number")

    # OK, now it gest more complicated, because we only want to keep one
    # instance per combination of game, lm, and round
    unique = {}
    for instance in instances:
        key = (instance.tournament_name, instance.get_lm_name(), instance.round_number)
        if key not in unique:
            unique[key] = instance
    instances = list(unique.values())
    print(f"Filtered to {len(instances)} instances after deduplication for game repetitions")

    batch = InstanceBatch(instances=instances)
    args.output_file.write_text(batch.model_dump_json())
    print(f"Wrote {len(instances)} instances to {args.output_file}")
