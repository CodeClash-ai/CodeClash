import re
import subprocess
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm.auto import tqdm

from codeclash.agents.player import Player
from codeclash.arenas.arena import CodeArena, RoundStats
from codeclash.constants import DIR_WORK, RESULT_TIE

BC_LOG = "sim_{idx}.log"
BC_FOLDER = "mysubmission"
BC_TIE = "Reason: The winning team won arbitrarily (coin flip)."


class BattleCode25Arena(CodeArena):
    name: str = "BattleCode25"
    description: str = """BattleCode 2025 throws you into a real-time strategy showdown where your Python bot pilots a team of specialized robots—Soldiers, Moppers, Splashers—alongside towers that spawn units or generate resources.
Your mission: paint over 70% of the map (or eliminate the enemy) by coordinating cleanups, area cover, and tower-building through tight bytecode budgets and clever unit synergy."""
    default_args: dict = {
        "maps": "quack",
    }
    submission: str = "src/mysubmission"

    def __init__(self, config, **kwargs):
        super().__init__(config, **kwargs)
        assert len(config["players"]) == 2, "BattleCode25 is a two-player game"
        self.run_cmd_round: str = "python run.py run"
        for arg, val in self.game_config.get("args", self.default_args).items():
            if isinstance(val, bool):
                if val:
                    self.run_cmd_round += f" --{arg}"
            else:
                self.run_cmd_round += f" --{arg} {val}"

    def _run_single_simulation(self, agents: list[Player], idx: int, cmd: str) -> str:
        try:
            response = self.environment.execute(cmd + f" > {self.log_env / BC_LOG.format(idx=idx)}")
        except subprocess.TimeoutExpired:
            self.logger.warning(f"BattleCode simulation {idx} timed out: {cmd}")
            return ""
        if response["returncode"] != 0:
            self.logger.warning(
                f"BattleCode simulation {idx} failed with exit code {response['returncode']}:\n{response['output']}"
            )
        return response["output"]

    def execute_round(self, agents: list[Player]):
        for agent in agents:
            src, dest = f"/{agent.name}/src/{BC_FOLDER}/", str(DIR_WORK / "src" / agent.name)
            self.environment.execute(f"rm -rf {dest}; cp -r {src} {dest}")
        args = [f"--p{idx + 1}-dir src --p{idx + 1} {agent.name}" for idx, agent in enumerate(agents)]
        cmd = f"{self.run_cmd_round} {' '.join(args)}"
        self.logger.info(f"Running game: {cmd}")

        with ThreadPoolExecutor(5) as executor:
            # Submit all simulations to the thread pool
            futures = [
                executor.submit(self._run_single_simulation, agents, idx, cmd)
                for idx in range(self.game_config["sims_per_round"])
            ]
            # Collect results as they complete
            for future in tqdm(as_completed(futures), total=len(futures), desc="Simulations"):
                future.result()

    def get_results(self, agents: list[Player], round_num: int, stats: RoundStats):
        scores = defaultdict(int)
        for idx in range(self.game_config["sims_per_round"]):
            with open(self.log_round(round_num) / BC_LOG.format(idx=idx)) as f:
                lines = f.read().strip().split("\n")
            if len(lines) < 3:
                # Game likely crashed, skip this simulation
                continue
            # Get the third-to-last line which contains the winner info
            winner_line = lines[-3]
            reason_line = lines[-2]
            match = re.search(r"\s\((.*)\)\swins\s\(", winner_line)
            if match and reason_line != BC_TIE:
                winner_key = match.group(1)
                # Map A/B to actual agent names (much closer to original code)
                winner = {"A": agents[0].name, "B": agents[1].name}.get(winner_key, RESULT_TIE)
                scores[winner] += 1
            else:
                winner = RESULT_TIE

        stats.winner = max(scores, key=scores.get)
        stats.scores = scores
        for player, score in stats.scores.items():
            stats.player_stats[player].score = score

    def validate_code(self, agent: Player) -> tuple[bool, str | None]:
        if BC_FOLDER not in agent.environment.execute("ls src")["output"]:
            return False, f"There should be a `src/{BC_FOLDER}/` directory"
        if "bot.py" not in agent.environment.execute(f"ls src/{BC_FOLDER}")["output"]:
            return False, f"There should be a `src/{BC_FOLDER}/bot.py` file"
        bot_content = agent.environment.execute(f"cat src/{BC_FOLDER}/bot.py")["output"].splitlines()
        if "def turn():" not in bot_content:
            return False, f"There should be a `turn()` function implemented in `src/{BC_FOLDER}/bot.py`"
        return True, None
