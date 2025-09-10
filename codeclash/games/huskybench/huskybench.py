from pathlib import Path

from codeclash.agents.player import Player
from codeclash.games.game import CodeGame, RoundStats
from codeclash.utils.environment import copy_from_container

HB_LOG_DIR = Path("/testbed/engine/logs/")


class HuskyBenchGame(CodeGame):
    name: str = "HuskyBench"

    def __init__(self, config, *, tournament_id: str, local_output_dir: Path):
        super().__init__(config, tournament_id=tournament_id, local_output_dir=local_output_dir)
        self.run_cmd_round: str = (
            f"python engine/main.py --port 8000 --sim --sim-rounds {self.game_config['sims_per_round']}"
        )
        for arg, val in self.game_config.get("args", {}).items():
            if isinstance(val, bool):
                if val:
                    self.run_cmd_round += f" --{arg}"
            else:
                self.run_cmd_round += f" --{arg} {val}"

    def copy_logs_from_env(self, round_num):
        super().copy_logs_from_env(round_num)
        log_path = self.log_round(round_num)
        copy_from_container(
            container=self.environment,
            src_path=HB_LOG_DIR,
            dest_path=log_path,
        )

    def get_stats(self, agents: list[Player], round_num: int) -> RoundStats:
        return RoundStats(winner="N/A", scores={})

    def execute_round(self, agents: list[Player]):
        self.environment.execute(f"rm -rf {HB_LOG_DIR}; mkdir -p {HB_LOG_DIR}")
        try:
            self.logger.debug("Starting game servers")
            self.environment.execute(f"{self.run_cmd_round} > {HB_LOG_DIR / 'engine.log'} &")
            for agent in agents:
                self.environment.execute(
                    f"python client/main.py --port 8000 > {HB_LOG_DIR / f'{agent.name}.log'} &", cwd=f"/{agent.name}"
                )
        finally:
            # Kill all python servers when done
            self.environment.execute("pkill -f 'python client/main.py' || true")
            self.environment.execute("pkill -f 'python engine/main.py' || true")
