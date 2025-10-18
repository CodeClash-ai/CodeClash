import re
import shlex
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm.auto import tqdm

from codeclash.agents.player import Player
from codeclash.constants import RESULT_TIE
from codeclash.games.game import CodeGame, RoundStats

HALITE_LOG = "sim_{idx}.log"


class HaliteGame(CodeGame):
    name: str = "Halite"
    description: str = """Halite is a strategic programming game where players write bots to control ships that gather resources, build structures, and compete for dominance on a grid-based map.
Victory is achieved by outmaneuvering opponents, optimizing resource collection, and strategically expanding your territory"""
    default_args: dict = {}

    def __init__(self, config, **kwargs):
        super().__init__(config, **kwargs)
        self.run_cmd_round: str = f"./environment/halite --replaydirectory {self.log_env}"
        for arg, val in self.game_config.get("args", self.default_args).items():
            if isinstance(val, bool):
                if val:
                    self.run_cmd_round += f" --{arg}"
            else:
                self.run_cmd_round += f" --{arg} {val}"

    def _run_single_simulation(self, agents: list[Player], idx: int, cmd: str):
        """Run a single halite simulation and return the output."""
        cmd = f"{cmd} > {self.log_env / HALITE_LOG.format(idx=idx)}"

        # Run the simulation and return the output
        try:
            response = self.environment.execute(cmd, timeout=120)
        except subprocess.TimeoutExpired:
            self.logger.warning(f"Halite simulation {idx} timed out: {cmd}")
            return
        if response["returncode"] != 0:
            self.logger.warning(
                f"Halite simulation {idx} failed with exit code {response['returncode']}:\n{response['output']}"
            )

    def execute_round(self, agents: list[Player]):
        entries = []
        for agent in agents:
            entries.append(f"python /{agent.name}/airesources/Python/RandomBot.py")
        cmd = f"{self.run_cmd_round} {shlex.join(entries)}"
        self.logger.info(f"Running game: {cmd}")
        with ThreadPoolExecutor(5) as executor:
            futures = [
                executor.submit(self._run_single_simulation, agents, idx, cmd)
                for idx in range(self.game_config["sims_per_round"])
            ]
            for future in tqdm(as_completed(futures), total=len(futures)):
                future.result()

    def get_results(self, agents: list[Player], round_num: int, stats: RoundStats):
        winners = []
        pattern = r"Player\s#(\d+),\s(.*),\scame\sin\srank\s#(\d+)"
        for idx in range(self.game_config["sims_per_round"]):
            log_file = self.log_round(round_num) / HALITE_LOG.format(idx=idx)
            with open(log_file) as f:
                lines = f.readlines()[-len(agents) - 1 :]
                for line in lines:
                    match = re.search(pattern, line)
                    if match:
                        player_idx = int(match.group(1)) - 1
                        rank = int(match.group(3))
                        if rank == 1:
                            winners.append(agents[player_idx].name)

        # Count wins
        win_counts = Counter(winners)

        # Find all winners with the maximum count
        max_wins = max(win_counts.values(), default=0)
        overall_winners = [name for name, count in win_counts.items() if count == max_wins]

        # Update stats
        stats.winner = RESULT_TIE if len(overall_winners) > 1 else overall_winners[0]
        stats.scores = dict(win_counts)
        for player, score in win_counts.items():
            if player != RESULT_TIE:
                stats.player_stats[player].score = score

    def validate_code(self, agent: Player) -> tuple[bool, str | None]:
        return True, None
