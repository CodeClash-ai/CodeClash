from pathlib import Path

from codeclash.agents.player import Player
from codeclash.games.game import CodeGame, RoundStats


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

    def get_stats(self, result_outputs: list[str], agents: list[Player]) -> RoundStats:
        return RoundStats(winner="N/A", scores={})

    def execute_round(self, agents: list[Player]):
        try:
            self.logger.debug("Starting game servers")
            self.environment.execute(self.run_cmd_round + " > output.log &")
            for agent in agents:
                self.environment.execute("python client/main.py --port 8000 &", cwd=f"/{agent.name}")
        finally:
            # Kill all python servers when done
            self.environment.execute("pkill -f 'python client/main.py' || true")
            self.environment.execute("pkill -f 'python engine/main.py' || true")
