import shlex
from collections import Counter
from pathlib import Path

from codeclash.agents.abstract import Player
from codeclash.constants import RESULT_TIE
from codeclash.games.abstract import CodeGame, RoundData, RoundStats


class RobotRumbleGame(CodeGame):
    name: str = "RobotRumble"

    def __init__(self, config, *, tournament_id: str, local_output_dir: Path):
        super().__init__(config, tournament_id=tournament_id, local_output_dir=local_output_dir)
        assert len(config["players"]) == 2, "RobotRumble is a two-player game"
        self.run_cmd_round: str = "./rumblebot run term"

    def get_stats(self, result_outputs: list[str], agents: list[Player]) -> RoundStats:
        winners = []
        for ro in result_outputs:
            lines = ro.strip().split("\n")

            # Get the last 2 lines which contain the game result (same as original)
            relevant_lines = lines[-2:] if len(lines) >= 2 else lines
            log_text = "\n".join(relevant_lines)

            if "Blue won" in log_text:
                winner = agents[0].name
                winners.append(winner)
            elif "Red won" in log_text:
                winner = agents[1].name
                winners.append(winner)
            elif "it was a tie" in log_text:
                winners.append(RESULT_TIE)
            else:
                winners.append(RESULT_TIE)

        # Count occurrences of each winner
        counts = Counter(winners)

        # Find all winners with the maximum count
        max_count = max(counts.values())
        top_winners = [w for w, c in counts.items() if c == max_count]

        # If multiple winners have the same count, return RESULT_TIE
        final_winner = RESULT_TIE if len(top_winners) > 1 else top_winners[0]

        return RoundStats(winner=final_winner, scores=dict(counts))

    def execute_round(self, agents: list[Player]) -> RoundData:
        outputs = []
        args = [f"/{agent.name}/robot.py" for agent in agents]
        cmd = f"{self.run_cmd_round} {shlex.join(args)}"
        self.logger.info(f"Running game: {cmd}")
        for _ in range(self.game_config.get("sims_per_round", 100)):
            response = self.environment.execute(cmd)
            assert response["returncode"] == 0, response
            outputs.append(response["output"])
        # For RobotRumble, log_outputs and result_outputs are the same
        return RoundData(logs=outputs, results=outputs)
