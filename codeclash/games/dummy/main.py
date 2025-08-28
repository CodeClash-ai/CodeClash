import re

from codeclash.agents.abstract import Player
from codeclash.games.abstract import CodeGame, RoundData, RoundStats


class DummyGame(CodeGame):
    name: str = "DummyGame"

    def get_stats(self, result_outputs: list[str], agents: list[Player]) -> RoundStats:
        result_output = result_outputs[0]  # Get the first (and only) element
        lines = result_output.split("FINAL_RESULTS")[-1].splitlines()

        scores = {}
        for line in lines:
            match = re.search(r"Bot\_(\d)\_main:\s(\d+)\srounds\swon", line)
            if match:
                bot_id = match.group(1)
                rounds_won = int(match.group(2))
                scores[agents[int(bot_id) - 1].name] = rounds_won

        return RoundStats(
            winner=max(scores, key=scores.get) if scores else "unknown",
            scores=scores,
            details={"dummy": True},
        )

    def execute_round(self, agents: list[Player]) -> RoundData:
        args = [f"/{agent.name}/main.py" for agent in agents]
        cmd = f"python engine.py {' '.join(args)} -r {self.game_config['sims_per_round']}"
        self.logger.info(f"Running game: {cmd}")
        response = self.environment.execute(cmd)
        assert response["returncode"] == 0, response
        return RoundData(logs=[response["output"]], results=[response["output"]])
