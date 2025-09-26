import argparse
import json
from pathlib import Path

import yaml

from codeclash.games import (
    BattleCodeGame,
    BattleSnakeGame,
    CodeGame,
    CoreWarGame,
    HuskyBenchGame,
    RoboCodeGame,
    RobotRumbleGame,
)


class IncludeTag:
    def __init__(self, value):
        self.value = value


class LiteralString(str):
    pass


def include_representer(dumper, data):
    return dumper.represent_scalar("!include", data.value)


def literal_representer(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


yaml.add_representer(IncludeTag, include_representer)
yaml.add_representer(LiteralString, literal_representer)
yaml.SafeDumper.add_representer(IncludeTag, include_representer)
yaml.SafeDumper.add_representer(LiteralString, literal_representer)

ARENAS: list[CodeGame] = [
    BattleCodeGame,
    BattleSnakeGame,
    CoreWarGame,
    HuskyBenchGame,
    RoboCodeGame,
    RobotRumbleGame,
]

NUM_TOURNAMENTS = 10


def prompt_game_desc(arena, rounds):
    # Return as a LiteralString to get proper YAML literal block scalar formatting
    content = f"""You are a software developer ({{{{player_id}}}}) competing in a coding game called {arena.name}.
{arena.description}

The game is played in {rounds} rounds. For every round, you (and your competitors) edit program code that controls your bot. This is round {{{{round}}}}.
After you and your competitor finish editing your codebases, the game is run automatically.

Your task: improve the bot in `{arena.submission}`, located in {{{{working_dir}}}}.
{{{{working_dir}}}} is your codebase, which contains both your both and supporting assets.
All of your commands will be executed in the {{{{working_dir}}}} directory (see notes below)."""
    return LiteralString(content)


def get_name(p):
    return p["model_name"].split("/")[-1]


def main(models, rounds, simulations, output: Path):
    # Get all unique pairs of models
    models = yaml.safe_load(open(models))
    output.mkdir(parents=True, exist_ok=True)
    pairs = []
    for i in range(len(models)):
        for j in range(i + 1, len(models)):
            pairs.append((models[i], models[j]))

    tracking_dict = {}
    for arena in ARENAS:
        tracking_dict[arena.name] = {}
        for pair in pairs:
            config = {
                "tournament": {
                    "rounds": rounds,
                },
                "game": {
                    "name": arena.name,
                    "sims_per_round": simulations,
                    "args": arena.default_args,
                },
                "players": [
                    {
                        "agent": "mini",
                        "name": get_name(p),
                        "config": {"agent": IncludeTag("mini/semi_prescriptive.yaml"), "model": p},
                    }
                    for p in pair
                ],
                "prompts": {"game_description": prompt_game_desc(arena, rounds)},
            }
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

            # Post-process to remove quotes around include paths
            with open(output / config_name) as f:
                content = f.read()

            # Remove quotes around include paths
            content = content.replace("!include 'mini/", "!include mini/")
            content = content.replace(".yaml'", ".yaml")

            with open(output / config_name, "w") as f:
                f.write(content)

            pvp = ".".join(sorted([get_name(pair[0]), get_name(pair[1])]))
            tracking_key = f"r{rounds}.s{simulations}.p2.{pvp}"
            tracking_dict[arena.name][tracking_key] = 0

    with open("configs/scripts/main_tracker.json", "w") as f:
        json.dump(tracking_dict, f, indent=2)
    print("Wrote tracking file to 'configs/scripts/main_tracker.json'.")

    print(f"Generated {len(pairs) * len(ARENAS)} configuration files in '{output}'.")
    print(f"- # Models: {len(models)}")
    print(f"- # Arenas: {len(ARENAS)}")
    print(f"- r (rounds) {rounds}")
    print(f"- s (sims_per_round) {simulations}")
    total_rounds = (len(models) * (len(models) - 1) // 2) * rounds * len(ARENAS)

    print("\n(Assuming each tournament is run once)")
    print(f"- Total rounds played across all models: {total_rounds}")
    rounds_per_model = total_rounds // len(models)
    print(f"- Each model: {rounds_per_model}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate configuration files.")
    parser.add_argument(
        "-m",
        "--models",
        type=str,
        default="configs/scripts/models.yaml",
        help="Path to model configurations.",
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
        "-o",
        "--output",
        type=Path,
        default=Path("configs/main/"),
        help="Output directory for configuration files (default: main/).",
    )
    args = parser.parse_args()
    main(**vars(args))
