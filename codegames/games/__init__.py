from codegames.games.abstract import CodeGame
from codegames.games.battlesnake.main import BattlesnakeGame
from codegames.games.corewars.main import CoreWarsGame
from codegames.games.robocode.main import RoboCodeGame


def get_game(config: dict) -> CodeGame:
    game = {
        "battlesnake": BattlesnakeGame,
        "corewars": CoreWarsGame,
        "robocode": RoboCodeGame,
    }.get(config["game"]["name"])
    if game is None:
        raise ValueError(f"Unknown game: {config['game']['name']}")
    return game(config)