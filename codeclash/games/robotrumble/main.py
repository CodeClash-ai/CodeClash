from pathlib import Path

from codeclash.agents.abstract import Player
from codeclash.constants import RESULT_TIE
from codeclash.games.abstract import CodeGame


class RobotRumbleGame(CodeGame):
    name: str = "RobotRumble"

    def __init__(self, config, *, tournament_id: str, local_output_dir: Path):
        super().__init__(
            config, tournament_id=tournament_id, local_output_dir=local_output_dir
        )
        assert len(config["players"]) == 2, "RobotRumble is a two-player game"
        self.run_cmd_round: str = "./rumblebot run term"

    def determine_winner(
        self, result_output: str, agents: list[Player]
    ) -> dict[str, str]:
        self.logger.debug(f"Determining winner from result output: {result_output}")
        lines = result_output.strip().split("\n")
        # Get the last 2 lines which contain the game result (same as original)
        relevant_lines = lines[-2:] if len(lines) >= 2 else lines
        log_text = "\n".join(relevant_lines)
        self.logger.debug(f"Relevant lines: {log_text}")

        if "Blue won" in log_text:
            winner = agents[0].name
            self.logger.debug(f"Blue won - Concluding winner: {winner}")
            return {"winner": winner}
        elif "Red won" in log_text:
            winner = agents[1].name
            self.logger.debug(f"Red won - Concluding winner: {winner}")
            return {"winner": winner}
        elif "it was a tie" in log_text:
            self.logger.debug("Game was a tie")
            return {"winner": RESULT_TIE}
        else:
            self.logger.debug("No clear result found, treating as tie")
            return {"winner": RESULT_TIE}

    def execute_round(self, agents: list[Player]) -> dict[str, str]:
        args = [f"/{agent.name}/robot.py" for agent in agents]
        cmd = f"{self.run_cmd_round} {' '.join(args)}"
        self.logger.info(f"Running command: {cmd}")
        response = self.environment.execute(cmd)
        assert response["returncode"] == 0, response
        # For RobotRumble, log_output and result_output are the same
        output = response["output"]
        return {"log_output": output, "result_output": output}
