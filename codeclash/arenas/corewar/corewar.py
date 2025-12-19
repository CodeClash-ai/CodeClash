import re
import shlex
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from codeclash.agents.player import Player
from codeclash.arenas.arena import CodeArena, RoundStats
from codeclash.constants import RESULT_TIE

COREWAR_LOG = "sim_{idx}.log"


class CoreWarArena(CodeArena):
    name: str = "CoreWar"
    description: str = """CoreWar is a programming battle where you write "warriors" in an assembly-like language called Redcode to compete within a virtual machine (MARS), aiming to eliminate your rivals by making their code self-terminate.
Victory comes from crafting clever tactics—replicators, scanners, bombers—that exploit memory layout and instruction timing to control the core."""
    submission: str = "warrior.red"

    def __init__(self, config, **kwargs):
        super().__init__(config, **kwargs)
        self.run_cmd_round: str = "./src/pmars"
        for arg, val in self.game_config.get("args", self.default_args).items():
            if isinstance(val, bool):
                if val:
                    self.run_cmd_round += f" -{arg}"
            else:
                self.run_cmd_round += f" -{arg} {val}"

    def _run_single_simulation(self, agents: list[Player], idx: int):
        # Shift agents by idx to vary starting positions
        agents = agents[idx:] + agents[:idx]
        args = [f"/{agent.name}/{self.submission}" for agent in agents]
        cmd = (
            f"{self.run_cmd_round} {shlex.join(args)} "
            f"-r {self.game_config['sims_per_round']} "
            f"> {self.log_env / COREWAR_LOG.format(idx=idx)};"
        )
        self.logger.info(f"Running game: {cmd}")
        response = self.environment.execute(cmd)
        assert response["returncode"] == 0, response

    def execute_round(self, agents: list[Player]):
        with ThreadPoolExecutor(4) as executor:
            futures = [executor.submit(self._run_single_simulation, agents, idx) for idx in range(len(agents))]
            for future in as_completed(futures):
                future.result()

    def get_results(self, agents: list[Player], round_num: int, stats: RoundStats):
        scores, wins = defaultdict(int), defaultdict(int)
        for idx in range(len(agents)):
            shift = agents[idx:] + agents[:idx]  # Shift agents by idx to match simulation order
            with open(self.log_round(round_num) / COREWAR_LOG.format(idx=idx)) as f:
                result_output = f.read()

            # Get the last n lines which contain the scores (closer to original)
            lines = result_output.strip().split("\n")
            relevant_lines = lines[-len(shift) * 2 :] if len(lines) >= len(shift) * 2 else lines
            relevant_lines = [l for l in relevant_lines if len(l.strip()) > 0]

            # Go through each line; score position is correlated with agent index
            for i, line in enumerate(relevant_lines):
                match = re.search(r".*\sby\s.*\sscores\s(\d+)", line)
                if match:
                    scores[shift[i].name] += int(match.group(1))

            # Last line corresponds to absolute number of wins
            last = relevant_lines[-1][len("Results:") :].strip()
            for i, w in enumerate(last.split()[:-1]):  # NOTE: Omitting ties (last entry)
                wins[shift[i].name] += int(w)

        if len(wins) != len(agents):
            # Should not happen
            self.logger.error(f"Have {len(wins)} wins but {len(agents)} agents")

        # Bookkeeping
        stats.scores = {a.name: wins[a.name] for a in agents}
        for a in agents:
            stats.player_stats[a.name].score = wins[a.name]

        # Determine overall winner by highest wins, then highest score
        max_wins = max(wins.values(), default=0)
        potential_winners = [name for name, w in wins.items() if w == max_wins]
        if len(potential_winners) == 1:
            stats.winner = potential_winners[0]
        else:
            # Tie-break by score
            max_score = -1
            winner = RESULT_TIE
            for name in potential_winners:
                if scores[name] > max_score:
                    max_score = scores[name]
                    winner = name
                elif scores[name] == max_score:
                    winner = RESULT_TIE
            stats.winner = winner

    def validate_code(self, agent: Player) -> tuple[bool, str | None]:
        if self.submission not in agent.environment.execute("ls")["output"]:
            return False, f"There should be a `{self.submission}` file"
        # Play game against a simple default bot to ensure it runs
        test_run_cmd = f"{self.run_cmd_round} {self.submission} /home/dwarf.red"
        test_run = agent.environment.execute(test_run_cmd, timeout=60)["output"]
        if any([l.startswith("Error") for l in test_run.split("\n")]):
            return False, f"The `{self.submission}` file is malformed (Ran `{test_run_cmd}`):\n{test_run}"
        return True, None
