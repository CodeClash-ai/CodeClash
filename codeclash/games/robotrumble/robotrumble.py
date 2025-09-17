import shlex
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from tqdm.auto import tqdm

from codeclash.agents.player import Player
from codeclash.constants import RESULT_TIE
from codeclash.games.game import CodeGame, RoundStats


class RobotRumbleGame(CodeGame):
    name: str = "RobotRumble"

    def __init__(self, config, *, tournament_id: str, local_output_dir: Path):
        super().__init__(config, tournament_id=tournament_id, local_output_dir=local_output_dir)
        assert len(config["players"]) == 2, "RobotRumble is a two-player game"
        self.run_cmd_round: str = "./rumblebot run term"

    def _run_single_simulation(self, agents: list[Player], idx: int) -> str:
        """Run a single robotrumble simulation and return the output."""
        args = [f"/{agent.name}/robot.py" for agent in agents]
        cmd = f"{self.run_cmd_round} {shlex.join(args)} > {self.log_env / f'sim_{idx}.txt'}"

        output = self.environment.execute(cmd)
        if output["returncode"] != 0:
            self.logger.warning(
                f"RobotRumble simulation {idx} failed with exit code {output['returncode']}:\n{output['output']}"
            )
        return output["output"]

    def execute_round(self, agents: list[Player]):
        self.logger.info(f"Running game with players: {[agent.name for agent in agents]}")

        with ThreadPoolExecutor(20) as executor:
            # Submit all simulations to the thread pool
            futures = [
                executor.submit(self._run_single_simulation, agents, idx)
                for idx in range(self.game_config.get("sims_per_round", 100))
            ]

            # Collect results as they complete
            for future in tqdm(as_completed(futures), total=len(futures)):
                future.result()

    def get_results(self, agents: list[Player], round_num: int, stats: RoundStats):
        winners = []
        for idx in range(self.game_config.get("sims_per_round", 100)):
            output_file = self.log_round(round_num) / f"sim_{idx}.txt"
            if not output_file.exists():
                self.logger.warning(f"Simulation {idx} not found, skipping")
                continue
            with open(output_file) as f:
                lines = f.read().strip().split("\n")

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

        # Update stats
        stats.winner = final_winner
        stats.scores = dict(counts)
        for player, score in counts.items():
            if player != RESULT_TIE:
                stats.player_stats[player].score = score

    def validate_code(self, agent: Player) -> tuple[bool, str | None]:
        if "robot.py" not in agent.environment.execute("ls")["output"]:
            return False, "There should be a `robot.py` file"
        if "def robot(state, unit):" not in agent.environment.execute("cat robot.py")["output"]:
            return (
                False,
                "robot.py does not contain the required robot function. It should be defined as 'def robot(state, unit): ...'",
            )
        test_run_cmd = f"{self.run_cmd_round} robot.py robot.py -t 1"
        test_run = agent.environment.execute(test_run_cmd)["output"]
        if "Some errors occurred:" in test_run:
            return False, f"Running robot.py (with `{test_run_cmd}`) resulted in errors:\n{test_run}"
        return True, None
