from codeclash.games.battlecode.battlecode import BattleCodeGame
from codeclash.games.battlesnake.battlesnake import BattleSnakeGame
from codeclash.games.corewar.corewar import CoreWarGame
from codeclash.games.dummy.dummy_game import DummyGame
from codeclash.games.game import CodeGame
from codeclash.games.huskybench.huskybench import HuskyBenchGame
from codeclash.games.robocode.robocode import RoboCodeGame
from codeclash.games.robotrumble.robotrumble import RobotRumbleGame


# might consider postponing imports to avoid loading things we don't need
def get_game(config: dict, **kwargs) -> CodeGame:
    game = {
        x.name: x
        for x in [
            BattleCodeGame,
            BattleSnakeGame,
            CoreWarGame,
            DummyGame,
            HuskyBenchGame,
            RoboCodeGame,
            RobotRumbleGame,
        ]
    }.get(config["game"]["name"])
    if game is None:
        raise ValueError(f"Unknown game: {config['game']['name']}")
    return game(config, **kwargs)
