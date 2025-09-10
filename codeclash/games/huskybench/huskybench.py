import re
from pathlib import Path

from codeclash.agents.player import Player
from codeclash.games.game import CodeGame, RoundStats

HB_LOG_ENGINE = "engine.log"
HB_REGEX_SCORE = re.compile(r"Player\s(\d+)\sdelta\supdated\:[\d\s\-\+\=]+,\smoney\:\s\d+\s\-\>\s(\d+)")


class HuskyBenchGame(CodeGame):
    name: str = "HuskyBench"

    def __init__(self, config, *, tournament_id: str, local_output_dir: Path):
        super().__init__(config, tournament_id=tournament_id, local_output_dir=local_output_dir)
        self.num_players: int = len(config["players"])
        self.run_cmd_round: str = (
            f"python engine/main.py --port 8000 --players {self.num_players} "
            f"--sim --sim-rounds {self.game_config['sims_per_round']}"
        )
        for arg, val in self.game_config.get("args", {}).items():
            if isinstance(val, bool):
                if val:
                    self.run_cmd_round += f" --{arg}"
            else:
                self.run_cmd_round += f" --{arg} {val}"

    def get_results(self, agents: list[Player], round_num: int) -> RoundStats:
        map_id_to_agent = {}
        for agent in agents:
            with open(self.log_round(round_num) / f"{agent.name}.log") as f:
                for line in f:
                    if line.startswith("My id:"):
                        agent_id = line.strip().split()[-1]
                        map_id_to_agent[agent_id] = agent.name
        self.logger.info("Agent IDs: " + str(map_id_to_agent))

        with open(self.log_round(round_num) / HB_LOG_ENGINE) as f:
            score_updates = [
                (match.group(1), int(match.group(2))) for l in f.readlines() if (match := HB_REGEX_SCORE.search(l))
            ]
            map_id_to_score = {k: v for k, v in score_updates[-self.num_players :]}
        self.logger.info("Final Scores: " + str(map_id_to_score))
        agent_to_score = {map_id_to_agent[agent_id]: score for agent_id, score in map_id_to_score.items()}
        return RoundStats(winner=max(agent_to_score, key=agent_to_score.get), scores=agent_to_score)

    def execute_round(self, agents: list[Player]):
        try:
            cmd = f"{self.run_cmd_round} > {self.log_env / HB_LOG_ENGINE} &"
            self.logger.debug(f"Starting game engine with command: {cmd}")
            self.environment.execute(cmd)
            for agent in agents:
                cmd = f"python client/main.py --port 8000 > {self.log_env / f'{agent.name}.log'} &"
                self.logger.debug(f"Adding agent with command: {cmd}")
                self.environment.execute(cmd, cwd=f"/{agent.name}")
        finally:
            # Kill all python servers when done
            self.environment.execute("pkill -f 'python client/main.py' || true")
            self.environment.execute("pkill -f 'python engine/main.py' || true")
