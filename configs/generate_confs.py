import argparse
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


def include_representer(dumper, data):
    return dumper.represent_scalar("!include", data.value)


yaml.add_representer(IncludeTag, include_representer)

ARENAS: list[CodeGame] = [
    BattleCodeGame,
    BattleSnakeGame,
    CoreWarGame,
    HuskyBenchGame,
    RoboCodeGame,
    RobotRumbleGame,
]


def prompt_game_desc(arena, rounds):
    return f"""You are a software developer ({{{{player_id}}}}) competing in a coding game called {arena.name}.
{arena.description}

The game is played in {rounds} rounds. For every round, you (and your competitors) edit program code that controls your bot. This is round {{{{round}}}}.
After you and your competitor finish editing your codebases, the game is run automatically.

Your task: improve the bot in `{arena.submission}`, located in {{{{working_dir}}}}.
{{{{working_dir}}}} is your codebase, which contains both your both and supporting assets.
All of your commands will be executed in the {{{{working_dir}}}} directory (see notes below).
"""


def get_name(p):
    return p["model_name"].split("/")[-1]


def main(models, rounds, simulations, output):
    # Get all unique pairs of models
    models = yaml.safe_load(open(models))
    Path(output).mkdir(parents=True, exist_ok=True)
    pairs = []
    for i in range(len(models)):
        for j in range(i + 1, len(models)):
            pairs.append((models[i], models[j]))

    for arena in ARENAS:
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
                        "config": {"agent": IncludeTag("mini/default.yaml"), "model": p},
                    }
                    for p in pair
                ],
                "prompts": {"game_description": prompt_game_desc(arena, rounds)},
            }
            config_name = f"{arena.name}__{get_name(pair[0])}__{get_name(pair[1])}__r{rounds}__s{simulations}.yaml"
            with open(f"{output}/{config_name}", "w") as f:
                yaml.dump(config, f, default_style=None, sort_keys=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate configuration files.")
    parser.add_argument(
        "-m",
        "--models",
        type=str,
        default="configs/model_configs.yaml",
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
        type=str,
        default="configs/main/",
        help="Output directory for configuration files (default: main/).",
    )
    args = parser.parse_args()
    main(**vars(args))
