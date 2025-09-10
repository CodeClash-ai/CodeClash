import re
import shlex
from pathlib import Path

from codeclash.agents.player import Player
from codeclash.games.game import CodeGame, RoundStats

COREWAR_LOG = "sim.log"


class CoreWarGame(CodeGame):
    name: str = "CoreWar"

    def __init__(self, config, *, tournament_id: str, local_output_dir: Path):
        super().__init__(config, tournament_id=tournament_id, local_output_dir=local_output_dir)
        self.run_cmd_round: str = "./src/pmars"
        for arg, val in self.game_config.get("args", {}).items():
            if isinstance(val, bool):
                if val:
                    self.run_cmd_round += f" -{arg}"
            else:
                self.run_cmd_round += f" -{arg} {val}"

    def get_results(self, agents: list[Player], round_num: int) -> RoundStats:
        with open(self.log_round(round_num) / COREWAR_LOG) as f:
            result_output = f.read()
        self.logger.debug(f"Determining winner from result output: {result_output}")
        scores = []
        n = len(agents) * 2
        lines = result_output.strip().split("\n")

        # Get the last n lines which contain the scores (closer to original)
        relevant_lines = lines[-n:] if len(lines) >= n else lines
        relevant_lines = [l for l in relevant_lines if len(l.strip()) > 0]
        self.logger.debug(f"Relevant lines for scoring: {relevant_lines}")

        # Go through each line; we assume score position is correlated with agent index
        for line in relevant_lines:
            match = re.search(r".*\sby\s.*\sscores\s(\d+)", line)
            if match:
                score = int(match.group(1))
                scores.append(score)

        if scores:
            if len(scores) != len(agents):
                self.logger.error(f"Have {len(scores)} scores but {len(agents)} agents")
            return RoundStats(
                winner=agents[scores.index(max(scores))].name,
                scores={agent.name: score for agent, score in zip(agents, scores)},
                details={"stdout": "\n".join(relevant_lines)},
            )
        else:
            self.logger.debug("No scores found, returning unknown")
            return RoundStats(winner="unknown", scores={agent.name: 0 for agent in agents})

    def execute_round(self, agents: list[Player]):
        args = [f"/{agent.name}/warriors/warrior.red" for agent in agents]
        cmd = (
            f"{self.run_cmd_round} {shlex.join(args)} "
            f"-r {self.game_config['sims_per_round']} "
            f"> {self.log_env / COREWAR_LOG};"
        )
        self.logger.info(f"Running game: {cmd}")
        response = self.environment.execute(cmd)
        assert response["returncode"] == 0, response
