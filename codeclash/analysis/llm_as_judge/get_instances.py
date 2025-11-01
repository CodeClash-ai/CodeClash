#!/usr/bin/env python3

"""Get instances based on specific pattern."""

import argparse
from collections import defaultdict
from pathlib import Path

from codeclash.analysis.llm_as_judge.utils import InstanceBatch, get_instances

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path, help="Path to the input log dir")
    parser.add_argument("-o", "--output-file", type=Path, help="Path to the output file", default="instances.json")
    args = parser.parse_args()

    SELECTED_ROUNDS = [1, 2, 3, 5, 10, 12, 14, 15]
    SELECTED_GAMES = None  # ["BattleSnake"]  # Set to None to select all games
    NUMBER_OF_TOURNAMENTS = 1

    # first get all instances, then filter
    instances = sorted(get_instances(args.input_dir), key=lambda x: x.instance_id)
    print(f"Found {len(instances)} instances")
    if SELECTED_GAMES is not None:
        instances = [instance for instance in instances if instance.game_name in SELECTED_GAMES]
        print(f"Filtered to {len(instances)} instances because of game name")
    else:
        print("No game filtering applied (SELECTED_GAMES is None)")
    instances = [instance for instance in instances if instance.round_number in SELECTED_ROUNDS]
    print(f"Filtered to {len(instances)} instances because of round number")

    grouped = defaultdict(list)
    for instance in instances:
        model_name_player, model_name_opponent = instance.get_lm_name_self_opponent()
        if model_name_player == model_name_opponent:
            continue
        key = (instance.game_name, model_name_player, model_name_opponent, instance.round_number)
        grouped[key].append(instance)

    selected_instances = []
    for key, instance_list in grouped.items():
        if len(instance_list) < NUMBER_OF_TOURNAMENTS:
            print(f"Warning: Only found {len(instance_list)} instances for {key}, need {NUMBER_OF_TOURNAMENTS}")
        selected_count = min(len(instance_list), NUMBER_OF_TOURNAMENTS)
        selected_instances.extend(instance_list[:selected_count])

    instances = selected_instances
    unique_models = {instance.get_lm_name_self_opponent()[0] for instance in instances}
    print(
        f"Filtered to {len(instances)} instances after keeping {NUMBER_OF_TOURNAMENTS} for game repetitions for {len(unique_models)} unique model matchups"
    )

    batch = InstanceBatch(instances=instances)
    args.output_file.write_text(batch.model_dump_json())
    print(f"Wrote {len(instances)} instances to {args.output_file}")
