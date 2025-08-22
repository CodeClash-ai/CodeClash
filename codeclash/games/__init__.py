from codeclash.games.abstract import CodeGame
from codeclash.games.battlecode.main import BattleCodeGame
from codeclash.games.battlesnake.main import BattleSnakeGame
from codeclash.games.corewar.main import CoreWarGame
from codeclash.games.robocode.main import RoboCodeGame
from codeclash.games.robotrumble.main import RobotRumbleGame


# might consider postponing imports to avoid loading things we don't need
def get_game(config: dict, **kwargs) -> CodeGame:
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
    return game(config, **kwargs)
