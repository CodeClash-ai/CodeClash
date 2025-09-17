import re

from codeclash.agents.player import Player
from codeclash.games.game import CodeGame, RoundStats
from codeclash.utils.environment import create_file_in_container

HB_LOG_ENGINE = "engine.log"
HB_PORT = 8000
HB_REGEX_SCORE = re.compile(r"Player\s(\d+)\sdelta\supdated\:[\d\s\-\+\=]+,\smoney\:\s\d+\s\-\>\s(\d+)")
HB_SCRIPT = "run_game.sh"


class HuskyBenchGame(CodeGame):
    name: str = "HuskyBench"

    def __init__(self, config, **kwargs):
        super().__init__(config, **kwargs)
        self.num_players: int = len(config["players"])
        self.run_cmd_round: str = (
            f"python engine/main.py --port {HB_PORT} --players {self.num_players} "
            f"--sim --sim-rounds {self.game_config['sims_per_round']}"
        )
        for arg, val in self.game_config.get("args", {}).items():
            if isinstance(val, bool):
                if val:
                    self.run_cmd_round += f" --{arg}"
            else:
                self.run_cmd_round += f" --{arg} {val}"

    def _construct_game_script(self, agents: list[Player], run_cmd_round: str, verbose: bool = False) -> None:
        if verbose:
            self.logger.debug(f"Starting game engine with command: {run_cmd_round}")
        script = [
            "!/bin/bash",
            "rm -rf /app/output/*",  # Remove previous outputs
            f"kill -9 $(lsof -ti :{HB_PORT})",  # Kill previous game if any
            run_cmd_round,  # Start engine
            "sleep 0.5",  # Give engine a moment to start
        ]
        for agent in agents:
            # Start each agent in background, redirecting output to log file
            cmd = (
                f"cd /{agent.name} && python client/main.py --port {HB_PORT} "
                f"> {self.log_env / f'{agent.name}.log'} 2>&1 &"
            )
            if verbose:
                self.logger.debug(f"Starting agent {agent.name} with command: {cmd}")
            script.append(cmd)
        script.append("wait")
        script.append(f"mv /app/output/* {self.log_env}")  # Move logs to log directory
        return "\n".join(script)

    def execute_round(self, agents: list[Player]):
        cmd = f"{self.run_cmd_round} > {self.log_env / HB_LOG_ENGINE} 2>&1 &"
        script = self._construct_game_script(agents, cmd, verbose=True)
        create_file_in_container(container=self.environment, content=script, dest_path=f"/testbed/{HB_SCRIPT}")
        self.environment.execute(f"chmod +x {HB_SCRIPT}; ./{HB_SCRIPT}")

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
        assets = agent.environment.execute("ls client")["output"]
        if "main.py" not in assets:
            return False, "There should be a `client/main.py` file"
        if "player.py" not in assets:
            return False, "There should be a `client/player.py` file"
        return True, None
