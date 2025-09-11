import re
from pathlib import Path

from codeclash.agents.player import Player
from codeclash.games.game import CodeGame, RoundStats
from codeclash.utils.environment import create_file_in_container

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

    def execute_round(self, agents: list[Player]):
        cmd = f"{self.run_cmd_round} > {self.log_env / HB_LOG_ENGINE} 2>&1 &"
        self.logger.debug(f"Starting game engine with command: {cmd}")
        script = [cmd, "sleep 0.5"]
        for agent in agents:
            cmd = f"cd /{agent.name} && python client/main.py --port 8000 > {self.log_env / f'{agent.name}.log'} 2>&1 &"
            self.logger.info(f"Adding player {agent.name} with command: {cmd}")
            script.append(cmd)
        script.append("wait")
        create_file_in_container(
            container=self.environment, content="\n".join(script), dest_path="/testbed/run_game.sh"
        )

        current = self.environment.config.timeout
        self.environment.config.timeout = 60
        self.environment.execute("chmod +x run_game.sh; ./run_game.sh")
        self.environment.config.timeout = current

    def get_results(self, agents: list[Player], round_num: int, stats: RoundStats):
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
        scores = {map_id_to_agent[agent_id]: score for agent_id, score in map_id_to_score.items()}

        stats.winner = max(scores, key=scores.get)
        stats.scores = scores
        for player, score in scores.items():
            stats.player_stats[player].score = score

    def validate_code(self, agent: Player) -> tuple[bool, str | None]:
        # TODO: implement more checks
        return True, None
