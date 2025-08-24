from pathlib import Path

from codeclash.games.abstract import CodeGame
from codeclash.games.battlecode.main import BattleCodeGame
from codeclash.games.battlesnake.main import BattleSnakeGame
from codeclash.games.corewar.main import CoreWarGame
from codeclash.games.robocode.main import RoboCodeGame
from codeclash.games.robotrumble.main import RobotRumbleGame


# might consider postponing imports to avoid loading things we don't need
def get_game(config: dict, *, tournament_id: str, local_output_dir: Path) -> CodeGame:
    game = {
        x.name: x
        for x in [
            BattleCodeGame,
            BattleSnakeGame,
            CoreWarGame,
            RoboCodeGame,
            RobotRumbleGame,
        ]
    }.get(config["game"]["name"])
    if game is None:
        raise ValueError(f"Unknown game: {config['game']['name']}")
    return game(config, tournament_id=tournament_id, local_output_dir=local_output_dir)
