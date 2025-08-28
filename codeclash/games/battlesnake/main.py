import json
import time
from pathlib import Path

from tqdm.auto import tqdm

from codeclash.agents.abstract import Player
from codeclash.constants import RESULT_TIE
from codeclash.games.abstract import CodeGame, RoundData, RoundStats
from codeclash.utils.environment import assert_zero_exit_code


class BattleSnakeGame(CodeGame):
    name: str = "BattleSnake"

    def __init__(self, config, *, tournament_id: str, local_output_dir: Path):
        super().__init__(config, tournament_id=tournament_id, local_output_dir=local_output_dir)
        self.run_cmd_round: str = "./battlesnake play"
        for arg, val in self.game_config.get("args", {}).items():
            if isinstance(val, bool):
                if val:
                    self.run_cmd_round += f" --{arg}"
            else:
                self.run_cmd_round += f" --{arg} {val}"

    def get_stats(self, result_outputs: list[str], agents: list[Player]) -> RoundStats:
        winners = []
        for ro in result_outputs:
            lines = ro.strip().split("\n")
            last_line = lines[-1] if lines else ""  # Get the last line which contains the game result
            winner = json.loads(last_line)["winnerName"]
            winners.append(winner)

        win_counts = {agent.name: winners.count(agent.name) for agent in agents}
        max_wins = max(win_counts.values())
        winners = [name for name, wins in win_counts.items() if wins == max_wins]
        return RoundStats(
            winner=RESULT_TIE if len(winners) > 1 else winners[0],
            scores=win_counts,
        )

    def execute_round(self, agents: list[Player]) -> RoundData:
        cmd = []
        for idx, agent in enumerate(agents):
            port = 8001 + idx
            # Start server in background - just add & to run in background!
            self.environment.execute(f"PORT={port} python main.py &", cwd=f"/{agent.name}")
            cmd.append(f"--url http://0.0.0.0:{port} -n {agent.name}")

        time.sleep(3)  # Give servers time to start

        try:
            log_outputs, result_outputs = [], []
            cmd = self.run_cmd_round + " " + " ".join(cmd)
            self.logger.info(f"Running game: {cmd}")
            for idx in tqdm(range(self.game_config["sims_per_round"])):
                # Create temporary output file for results
                output_file = f"battlesnake_output_{idx}_{int(time.time())}.json"

                # Run game
                response = assert_zero_exit_code(
                    self.environment.execute(
                        cmd + f" -o {output_file}",
                        cwd=f"{self.environment.config.cwd}/game",
                    )
                )

                # Read the output file for result information
                result_response = self.environment.execute(f"cat game/{output_file}")
                result_output = result_response["output"]
                log_outputs.append(response["output"])
                result_outputs.append(result_output)

                # Clean up the output file
                self.environment.execute(f"rm -f game/{output_file}")
                time.sleep(0.05)

            return RoundData(logs=log_outputs, results=result_outputs)
        finally:
            # Kill all python servers when done
            self.environment.execute("pkill -f 'python main.py' || true")
