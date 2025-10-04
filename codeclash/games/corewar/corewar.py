import re
import shlex

from codeclash.agents.player import Player
from codeclash.games.game import CodeGame, RoundStats

COREWAR_LOG = "sim.log"


class CoreWarGame(CodeGame):
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

    def execute_round(self, agents: list[Player]):
        args = [f"/{agent.name}/{self.submission}" for agent in agents]
        cmd = (
            f"{self.run_cmd_round} {shlex.join(args)} "
            f"-r {self.game_config['sims_per_round']} "
            f"> {self.log_env / COREWAR_LOG};"
        )
        self.logger.info(f"Running game: {cmd}")
        response = self.environment.execute(cmd)
        assert response["returncode"] == 0, response

    def get_results(self, agents: list[Player], round_num: int, stats: RoundStats):
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
            stats.winner = agents[scores.index(max(scores))].name
            stats.scores = {agent.name: score for agent, score in zip(agents, scores)}
        else:
            self.logger.debug("No scores found, returning unknown")
            stats.winner = "unknown"
            stats.scores = {agent.name: 0 for agent in agents}

        for player, score in stats.scores.items():
            stats.player_stats[player].score = score

    def validate_code(self, agent: Player) -> tuple[bool, str | None]:
        if self.submission not in agent.environment.execute("ls")["output"]:
            return False, f"There should be a `{self.submission}` file"
        # Play game against a simple default bot to ensure it runs
        test_run_cmd = f"{self.run_cmd_round} {self.submission} /home/dwarf.red"
        test_run = agent.environment.execute(test_run_cmd)["output"]
        if any([l.startswith("Error") for l in test_run.split("\n")]):
            return False, f"The `{self.submission}` file is malformed (Ran `{test_run_cmd}`):\n{test_run}"
        return True, None
