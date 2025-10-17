import re
import subprocess

from codeclash.agents.player import Player
from codeclash.constants import DIR_WORK
from codeclash.games.game import CodeGame, RoundStats
from codeclash.utils.environment import create_file_in_container

HB_LOG_ENGINE = "engine.log"
HB_PORT = 8000
HB_REGEX_SCORE = re.compile(r"Player\s(\d+)\sdelta\supdated\:[\d\s\-\+\=]+,\smoney\:\s\d+\s\-\>\s(\d+)")
HB_SCRIPT = "run_game.sh"
HB_BOT_TIMEOUT = 10  # Max time (seconds) for a bot to run a single round


class HuskyBenchGame(CodeGame):
    name: str = "HuskyBench"
    description: str = f"""In this game, you will write code to control a poker-playing bot, aiming to outsmart your opponents and win chips.
Victory comes from crafting clever strategies—bluffing, reading opponents, and managing your chip stack effectively.
Be mindful of your bot's efficiency - your code should complete a simulation within 10 seconds to avoid forfeiting the round.
You can use {HB_SCRIPT} to check if your bot runs in time."""
    submission: str = "client/player.py"

    def __init__(self, config, **kwargs):
        super().__init__(config, **kwargs)
        self.num_players: int = len(config["players"])
        self.run_engine: str = (
            f"python engine/main.py --port {HB_PORT} --players {self.num_players} "
            f"--sim --sim-rounds {self.game_config['sims_per_round']}"
        )
        # Game timeout is number of sims * bot timeout
        self.timeout = self.game_config["sims_per_round"] * HB_BOT_TIMEOUT
        for arg, val in self.game_config.get("args", self.default_args).items():
            if isinstance(val, bool):
                if val:
                    self.run_engine += f" --{arg}"
            else:
                self.run_engine += f" --{arg} {val}"

    def _construct_game_script(
        self,
        agents: list[Player],
        run_client: str,
        run_engine: str,
        verbose: bool = False,
        log_outputs: bool = False,
    ) -> None:
        if verbose:
            self.logger.debug(f"Starting game engine with command: {run_engine}")
        script = [
            "#!/bin/bash",
            "rm -rf /app/output/*",  # Remove previous outputs
            f"kill -9 $(lsof -ti :{HB_PORT})",  # Kill previous game if any
            run_engine,  # Start engine
            "sleep 0.5",  # Give engine a moment to start
        ]
        for agent in agents:
            # Start each agent in background, redirecting output to log file
            _run_client = run_client.format(agent=agent, port=HB_PORT, log_dir=self.log_env)
            if verbose:
                self.logger.debug(f"Starting agent {agent.name} with command: {_run_client}")
            script.append(_run_client)
        script.append("wait")
        if log_outputs:
            script.append(f"mv /app/output/* {self.log_env}")  # Move logs to log directory
        return "\n".join(script)

    def execute_round(self, agents: list[Player]):
        # Use placeholders compatible with str.format; compute log dir separately
        run_client = "cd /{agent.name} && python client/main.py --port {port} > {log_dir}/{agent.name}.log 2>&1 &"
        run_engine = f"{self.run_engine} > {self.log_env / HB_LOG_ENGINE} 2>&1 &"
        script = self._construct_game_script(agents, run_client, run_engine, verbose=True, log_outputs=True)
        self.logger.info(f"Executing game script:\n{script}")
        create_file_in_container(container=self.environment, content=script, dest_path=DIR_WORK / HB_SCRIPT)
        self.logger.info(f"Running game script: ./{HB_SCRIPT}")
        self.environment.execute(f"chmod +x {HB_SCRIPT}; ./{HB_SCRIPT}", timeout=self.timeout)

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

        # Make sure bot can run (check against itself)
        run_engine = (
            self.run_engine.replace(f"--sim-rounds {self.game_config['sims_per_round']}", "--sim-rounds 1") + " &"
        )
        run_client = "python client/main.py --port {port} &"
        script = self._construct_game_script([agent, agent], run_client, run_engine, verbose=False)
        self.logger.info(f"Validating agent {agent.name} with script:\n{script}")
        create_file_in_container(container=agent.environment, content=script, dest_path=DIR_WORK / HB_SCRIPT)
        try:
            agent.environment.execute(f"chmod +x {HB_SCRIPT}; ./{HB_SCRIPT}", timeout=HB_BOT_TIMEOUT)
        except subprocess.TimeoutExpired:
            return (
                False,
                f"Your submission did not successfully complete a single round of poker within "
                f"the {HB_BOT_TIMEOUT} second time limit. Please reduce your bot's computation time."
                f"\n\nCommand run: ./{HB_SCRIPT}",
            )
        return True, None
