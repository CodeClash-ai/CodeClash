from codeclash.games.abstract import CodeGame
from codeclash.games.battlesnake.main import BattlesnakeGame
from codeclash.games.corewars.main import CoreWarsGame
from codeclash.games.robocode.main import RoboCodeGame
from codeclash.games.robotrumble.main import RobotRumbleGame


def get_game(config: dict) -> CodeGame:
    game = {
        BattlesnakeGame.name: BattlesnakeGame,
        CoreWarsGame.name: CoreWarsGame,
        RoboCodeGame.name: RoboCodeGame,
        RobotRumbleGame.name: RobotRumbleGame,
    }.get(config["game"]["name"])
    if game is None:
        raise ValueError(f"Unknown game: {config['game']['name']}")
    return game(config["game"])
