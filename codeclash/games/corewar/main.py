import re
from pathlib import Path

from codeclash.agents.abstract import Player
from codeclash.games.abstract import CodeGame


class CoreWarGame(CodeGame):
    name: str = "CoreWar"

    def __init__(self, config, *, tournament_id: str, local_output_dir: Path):
        super().__init__(
            config, tournament_id=tournament_id, local_output_dir=local_output_dir
        )
        self.run_cmd_round: str = "./src/pmars"
        for arg, val in self.game_config.get("args", {}).items():
            if isinstance(val, bool):
                if val:
                    self.run_cmd_round += f" -{arg}"
            else:
                self.run_cmd_round += f" -{arg} {val}"

    def determine_winner(
        self, result_output: str, agents: list[Player]
    ) -> dict[str, str]:
        self.logger.debug(f"Determining winner from result output: {result_output}")
        scores = []
        n = len(agents) * 2
        lines = result_output.strip().split("\n")
        # Get the last n lines which contain the scores (closer to original)
        relevant_lines = lines[-n:] if len(lines) >= n else lines
        self.logger.debug(f"Relevant lines for scoring: {relevant_lines}")

        for line in relevant_lines:
            match = re.search(r".*\sby\s.*\sscores\s(\d+)", line)
            if match:
                score = int(match.group(1))
                scores.append(score)
                self.logger.debug(f"Found score: {score} from line: {line}")

        self.logger.debug(f"All scores: {scores}")
        if scores:
            max_score_index = scores.index(max(scores))
            winner = agents[max_score_index].name
            self.logger.debug(
                f"Concluding winner: {winner} with index {max_score_index}"
            )
            return {"winner": winner}
        else:
            self.logger.debug("No scores found, returning unknown")
            return {"winner": "unknown"}

    def execute_round(self, agents: list[Player]) -> dict[str, str]:
        args = [f"/{agent.name}/warriors/warrior.red" for agent in agents]
        cmd = f"{self.run_cmd_round} {' '.join(args)}"
        self.logger.info(f"Running command: {cmd}")
        response = self.environment.execute(cmd)
        assert response["returncode"] == 0, response
        # For CoreWar, log_output and result_output are the same
        output = response["output"]
        return {"log_output": output, "result_output": output}
