import argparse
from pathlib import Path

import yaml

from codeclash.constants import DIR_WORK, OPPONENT_CODEBASES_DIR_NAME
from codeclash.games import (
    ARENAS,
    DummyGame,
)
from codeclash.utils.generate_confs import clean_config, get_config, get_name


def main(models: str, arenas: str, rounds: int, simulations: int, record_ratio: float, output: Path):
    # Get all models
    models = yaml.safe_load(open(models))
    output.mkdir(parents=True, exist_ok=True)
    pairs = []
    for i in range(len(models)):
        for j in range(i + 1, len(models)):
            pairs.append((models[i], models[j]))

    # Get arenas
    arenas_list = ARENAS if arenas == "all" else [a for a in ARENAS if a.name in arenas.split(",")]
    if DummyGame in arenas_list:
        arenas_list.remove(DummyGame)  # Skip DummyGame for config generation
    if not arenas_list:
        print(f"No valid arenas found from {arenas}. Choose from {[a.name for a in ARENAS]}.")
        return  # Stop execution if no valid arenas are found

    configs_created = 0
    for arena in arenas_list:
        print(f"Generating configs for arena: {arena.name}")
        for pair in pairs:
            print(f" - {[p['model_name'] for p in pair]}")
            config = get_config(rounds, simulations, arena, pair)

            # Inform model that it can see opponent's codebases
            config["tournament"]["transparent"] = True
            config["prompts"]["game_description"] += f"""
In this tournament, you have full access to your opponent(s)' codebase.
You can access their codebase(s) under /{OPPONENT_CODEBASES_DIR_NAME}/.
If you wish, you may read and analyze your opponent(s)' code to inform your strategy.
Note that:
- Your opponent(s) also has access to your codebase ({DIR_WORK})
- You are shown a *copy* of the opponent(s)' codebase from the prior round; any changes you make will not affect their actual code.
"""

            pair_names = "__".join(sorted([get_name(pair[0]), get_name(pair[1])]))
            config_name = f"{arena.name}__{pair_names}__r{rounds}__s{simulations}.yaml"
            with open(output / config_name, "w") as f:
                yaml.dump(
                    config,
                    f,
                    default_style=None,
                    sort_keys=False,
                    allow_unicode=True,
                    default_flow_style=False,
                    Dumper=yaml.SafeDumper,
                )
            clean_config(output / config_name)
            configs_created += 1

    print(f"Generated {configs_created} configuration files in '{output}'.")
    print(f"- # Models: {len(models)}")
    print(f"- # Arenas: {len(arenas_list)}")
    print(f"- r (rounds) {rounds}")
    print(f"- s (sims_per_round) {simulations}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate configuration files.")
    parser.add_argument(
        "-m",
        "--models",
        type=str,
        default="configs/models_transparent.yaml",
        help="Path to model configurations.",
    )
    parser.add_argument(
        "-a",
        "--arenas",
        type=str,
        default="all",
        help="Comma separated list of arenas to generate configs for (default: all).",
    )
    parser.add_argument(
        "-r",
        "--rounds",
        type=int,
        default=15,
        help="Number of rounds per tournament for the configuration (default: 15).",
    )
    parser.add_argument(
        "-s",
        "--simulations",
        type=int,
        default=1000,
        help="Number of simulations to run per round (default: 1000).",
    )
    parser.add_argument(
        "--record_ratio",
        type=float,
        default=1,
        help="Fraction of simulations to record (default: 1 = all).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("configs/transparent/"),
        help="Output directory for configuration files (default: multi/).",
    )
    args = parser.parse_args()
    main(**vars(args))
