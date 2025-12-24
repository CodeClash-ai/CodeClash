import subprocess

from codeclash.agents.player import Player
from codeclash.arenas.arena import RoundStats
from codeclash.arenas.halite.halite import HALITE_LOG, HaliteArena

HALITE_WIN_PATTERN = r"Player\s(\d+),\s'(\S+)',\swas\srank\s(\d+)"

# Command to be run in each agent's `submission/` folder to compile agent
MAP_FILE_TYPE_TO_COMPILE = {
    ".cpp": "cmake . && make",
    ".ml": "ocamlbuild -lib unix {name}.native",
    ".rs": "cargo build",
}

# Command to be run from `environment/` folder to run competition
MAP_FILE_TYPE_TO_RUN = {
    ".cpp": "{path}/{name}",
    ".ml": "{path}/{name}.native",
    ".rs": "{path}/target/debug/{name}",
}


class Halite3Arena(HaliteArena):
    name: str = "Halite3"
    description: str = """"""
    default_args: dict = {}
    submission: str = "submission"
    executable: str = "./game_engine/halite"

    def __init__(self, config, **kwargs):
        super().__init__(config, **kwargs)
        # Remove replaydirectory arg as Halite3 does not support it
        self.run_cmd_round: str = self.run_cmd_round.replace(f"--replaydirectory {self.log_env}", "")

    def _run_single_simulation(self, agents: list[Player], idx: int, cmd: str):
        """Run a single halite simulation and return the output."""
        cmd = f"{cmd} > {self.log_env / HALITE_LOG.format(idx=idx)} 2>&1"

        # Run the simulation and return the output
        try:
            response = self.environment.execute(cmd, timeout=120)
            self.environment.execute(f"mv errorlog*.log {self.log_env}", timeout=10)
        except subprocess.TimeoutExpired:
            self.logger.warning(f"Halite simulation {idx} timed out: {cmd}")
            return
        if response["returncode"] != 0:
            self.logger.warning(
                f"Halite simulation {idx} failed with exit code {response['returncode']}:\n{response['output']}"
            )

    def get_results(self, agents: list[Player], round_num: int, stats: RoundStats):
        return super().get_results(
            agents,
            round_num,
            stats,
            pattern=HALITE_WIN_PATTERN,
        )

    def validate_code(
        self,
        agent: Player,
    ):
        return super().validate_code(
            agent,
            MAP_FILE_TYPE_TO_COMPILE,
            MAP_FILE_TYPE_TO_RUN,
        )
