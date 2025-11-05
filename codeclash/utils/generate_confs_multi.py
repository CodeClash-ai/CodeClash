import argparse
from pathlib import Path

import yaml

from codeclash.arenas import ARENAS
from codeclash.utils.generate_confs import clean_config, get_config


def main(models: str, arenas: str, rounds: int, simulations: int, record_ratio: float, output: Path):
    # Get all models
    models = yaml.safe_load(open(models))
    output.mkdir(parents=True, exist_ok=True)

    # Get arenas
    arenas_list = ARENAS if arenas == "all" else [a for a in ARENAS if a.name in arenas.split(",")]
    if not arenas_list:
        print(f"No valid arenas found from {arenas}. Choose from {[a.name for a in ARENAS]}.")
        return  # Stop execution if no valid arenas are found

    for arena in arenas_list:
        print(f"Generating config for arena: {arena.name}")
        config = get_config(rounds, simulations, arena, models)
        config_name = f"{arena.name}__p{len(models)}__r{rounds}__s{simulations}.yaml"
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

    print(f"Generated {len(arenas_list)} configuration files in '{output}'.")
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
        default="configs/models_multi.yaml",
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
        default=Path("configs/multi/"),
        help="Output directory for configuration files (default: multi/).",
    )
    args = parser.parse_args()
    main(**vars(args))
