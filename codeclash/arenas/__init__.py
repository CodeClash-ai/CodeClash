from codeclash.arenas.arena import CodeArena
from codeclash.arenas.battlecode.battlecode import BattleCodeArena
from codeclash.arenas.battlesnake.battlesnake import BattleSnakeArena
from codeclash.arenas.corewar.corewar import CoreWarArena
from codeclash.arenas.dummy.dummy import DummyArena
from codeclash.arenas.halite.halite import HaliteArena

# from codeclash.games.halite2.halite2 import Halite2Game # WIP
# from codeclash.games.halite3.halite3 import Halite3Game # WIP
from codeclash.arenas.huskybench.huskybench import HuskyBenchArena
from codeclash.arenas.robocode.robocode import RoboCodeArena
from codeclash.arenas.robotrumble.robotrumble import RobotRumbleArena

ARENAS = [
    BattleCodeArena,
    BattleSnakeArena,
    CoreWarArena,
    DummyArena,
    HaliteArena,
    HuskyBenchArena,
    RoboCodeArena,
    RobotRumbleArena,
]


# might consider postponing imports to avoid loading things we don't need
def get_game(config: dict, **kwargs) -> CodeArena:
    game = {x.name: x for x in ARENAS}.get(config["game"]["name"])
    if game is None:
        raise ValueError(f"Unknown game: {config['game']['name']}")
    return game(config, **kwargs)
