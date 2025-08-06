from codeclash.games.abstract import CodeGame
from codeclash.games.battlesnake.main import BattleSnakeGame
from codeclash.games.corewars.main import CoreWarsGame
from codeclash.games.robocode.main import RoboCodeGame
from codeclash.games.robotrumble.main import RobotRumbleGame


def get_game(config: dict) -> CodeGame:
    game = {
        BattleSnakeGame.name: BattleSnakeGame,
        CoreWarsGame.name: CoreWarsGame,
        RoboCodeGame.name: RoboCodeGame,
        RobotRumbleGame.name: RobotRumbleGame,
    }.get(config["game"]["name"])
    if game is None:
        raise ValueError(f"Unknown game: {config['game']['name']}")
    return game(config["game"])
