from codeclash.arenas.arena import CodeArena
from codeclash.arenas.battlecode.battlecode import BattleCodeArena
from codeclash.arenas.battlesnake.battlesnake import BattleSnakeArena
from codeclash.arenas.corewar.corewar import CoreWarArena
from codeclash.arenas.dummy.dummy import DummyArena
from codeclash.arenas.halite.halite import HaliteArena
from codeclash.arenas.halite2.halite2 import Halite2Arena
from codeclash.arenas.halite3.halite3 import Halite3Arena
from codeclash.arenas.huskybench.huskybench import HuskyBenchArena
from codeclash.arenas.robocode.robocode import RoboCodeArena
from codeclash.arenas.robotrumble.robotrumble import RobotRumbleArena

ARENAS = [
    BattleCodeArena,
    BattleSnakeArena,
    CoreWarArena,
    DummyArena,
    HaliteArena,
    Halite2Arena,
    Halite3Arena,
    HuskyBenchArena,
    RoboCodeArena,
    RobotRumbleArena,
]


# might consider postponing imports to avoid loading things we don't need
def get_arena(config: dict, **kwargs) -> CodeArena:
    game = {x.name: x for x in ARENAS}.get(config["game"]["name"])
    if game is None:
        raise ValueError(f"Unknown game: {config['game']['name']}")
    return game(config, **kwargs)
