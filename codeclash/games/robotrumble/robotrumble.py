import json
import shlex
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm.auto import tqdm

from codeclash.agents.player import Player
from codeclash.constants import RESULT_TIE
from codeclash.games.game import CodeGame, RoundStats


class RobotRumbleGame(CodeGame):
    name: str = "RobotRumble"
    description: str = """RobotRumble is a turn-based coding battle where you program a team of robots in Python to move, attack, and outmaneuver your opponent on a grid.
Every decision is driven by your code, and victory comes from crafting logic that positions robots smartly, times attacks well, and adapts over the 100-turn match.
NOTE: Please ensure that your code runs efficiently (under 60 seconds). Code that exceeds this run time will automatically forfeit the round."""
    default_args: dict = {"raw": True}
    submission: str = "robot.js"

    def __init__(self, config, **kwargs):
        super().__init__(config, **kwargs)
        assert len(config["players"]) == 2, "RobotRumble is a two-player game"
        self.run_cmd_round: str = "./rumblebot run term"
        self.sim_ext = "txt"
        for arg, val in self.game_config.get("args", self.default_args).items():
            if isinstance(val, bool):
                if val:
                    self.run_cmd_round += f" --{arg}"
                    if arg == "raw":
                        self.sim_ext = "json"
            else:
                self.run_cmd_round += f" --{arg} {val}"

    def _run_single_simulation(self, agents: list[Player], idx: int, cmd: str) -> str:
        """Run a single robotrumble simulation and return the output."""
        cmd = f"{cmd} > {self.log_env / f'sim_{idx}.{self.sim_ext}'}"

        # https://github.com/emagedoc/CodeClash/issues/62 (timeouts)
        try:
            output = self.environment.execute(cmd, timeout=120)
        except subprocess.TimeoutExpired:
            self.logger.warning(f"RobotRumble simulation {idx} timed out: {cmd}")
            return ""
        if output["returncode"] != 0:
            self.logger.warning(
                f"RobotRumble simulation {idx} failed with exit code {output['returncode']}:\n{output['output']}"
            )
        return output["output"]

    def execute_round(self, agents: list[Player]):
        self.logger.info(f"Running game with players: {[agent.name for agent in agents]}")
        args = [f"/{agent.name}/{self.submission}" for agent in agents]
        cmd = f"{self.run_cmd_round} {shlex.join(args)}"

        with ThreadPoolExecutor(5) as executor:
            # Submit all simulations to the thread pool
            futures = [
                executor.submit(self._run_single_simulation, agents, idx, cmd)
                for idx in range(self.game_config.get("sims_per_round", 100))
            ]

            # Log command being run
            self.logger.info(f"Running game: {cmd}")

            # Collect results as they complete
            for future in tqdm(as_completed(futures), total=len(futures)):
                future.result()

    def _get_winner_txt(self, output_file: str, agents: list[Player]) -> str:
        try:
            with open(output_file) as f:
                lines = f.read().strip().split("\n")
        except Exception as e:
            self.logger.warning(f"Failed to read output from {output_file}: {e}")
            return RESULT_TIE  # TODO: should this be a tie?

        # Get the last 2 lines which contain the game result (same as original)
        relevant_lines = lines[-2:] if len(lines) >= 2 else lines
        log_text = "\n".join(relevant_lines)

        if "Blue won" in log_text:
            return agents[0].name
        elif "Red won" in log_text:
            return agents[1].name
        elif "it was a tie" in log_text:
            return RESULT_TIE
        return RESULT_TIE

    def _get_winner_json(self, output_file: str, agents: list[Player]) -> str:
        try:
            with open(output_file) as f:
                data = json.load(f)
        except json.JSONDecodeError:
            self.logger.warning(f"Failed to parse JSON output from {output_file}")
            return RESULT_TIE  # TODO: should this be a tie?
        if "winner" in data:
            if data["winner"] == "Blue":
                return agents[0].name
            elif data["winner"] == "Red":
                return agents[1].name
            else:
                return RESULT_TIE
        return RESULT_TIE

    def get_results(self, agents: list[Player], round_num: int, stats: RoundStats):
        winners = []
        for idx in range(self.game_config.get("sims_per_round", 100)):
            output_file = self.log_round(round_num) / f"sim_{idx}.{self.sim_ext}"
            if not output_file.exists():
                self.logger.warning(f"Simulation {idx} not found, skipping")
                continue
            winners.append(
                self._get_winner_txt(output_file, agents)
                if self.sim_ext == "txt"
                else self._get_winner_json(output_file, agents)
            )

        # Count occurrences of each winner
        counts = Counter(winners)

        # Find all winners with the maximum count
        max_count = max(counts.values())
        top_winners = [w for w, c in counts.items() if c == max_count]

        # If multiple winners have the same count, return RESULT_TIE
        final_winner = RESULT_TIE if len(top_winners) > 1 else top_winners[0]

        # Update stats
        stats.winner = final_winner
        stats.details.append(f"In this round, {agents[0].name} was Blue and {agents[1].name} was Red.")
        stats.scores = dict(counts)
        for player, score in counts.items():
            if player != RESULT_TIE:
                stats.player_stats[player].score = score

    def validate_code(self, agent: Player) -> tuple[bool, str | None]:
        if self.submission not in agent.environment.execute("ls")["output"]:
            return False, f"There should be a `{self.submission}` file"
        if "function robot(state, unit) {" not in agent.environment.execute(f"cat {self.submission}")["output"]:
            return (
                False,
                f"{self.submission} does not contain the required robot function. It should be defined as 'function robot(state, unit) {{ ... }}'.",
            )
        test_run_cmd = f"{self.run_cmd_round} {self.submission} {self.submission} -t 1"
        try:
            test_run = agent.environment.execute(test_run_cmd, timeout=60)["output"]
        except subprocess.TimeoutExpired:
            return (
                False,
                f"Running {self.submission} (with `{test_run_cmd}`) timed out (60 seconds). Please ensure your code runs efficiently.",
            )
        if "Some errors occurred:" in test_run:
            return False, f"Running {self.submission} (with `{test_run_cmd}`) resulted in errors:\n{test_run}"
        return True, None
