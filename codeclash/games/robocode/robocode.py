import random
import re
import subprocess
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from tqdm.auto import tqdm

from codeclash.agents.player import Player
from codeclash.games.game import CodeGame, RoundStats
from codeclash.utils.environment import create_file_in_container

RC_FILE = Path("MyTank.java")
SIMS_PER_RUN = 10


class RoboCodeGame(CodeGame):
    name: str = "RoboCode"
    description: str = f"""Robocode (Tank Royale) is a programming game where your code is the tank: each turn your bot sends intents—speed plus body/gun/radar turn rates and firepower—based on the game state it perceives via radar.
Your program decides how to move, aim, and fire in a deterministic, turn-based arena to outlast other bots.
Your bot logic must be written in Java and located in the `robots/custom/` directory.
Keep the main bot class named `{str(RC_FILE)}`, but you can include additional Java files if you'd like."""
    default_args: dict = {
        "nodisplay": True,
        "nosound": True,
    }
    submission: str = "robots/custom/"

    def __init__(self, config, **kwargs):
        super().__init__(config, **kwargs)
        self.run_cmd_round: str = "./robocode.sh"
        for arg, val in self.game_config.get("args", self.default_args).items():
            if isinstance(val, bool):
                if val:
                    self.run_cmd_round += f" -{arg}"
            else:
                self.run_cmd_round += f" -{arg} {val}"

    def _get_battle_config(self) -> str:
        default_battle_config = {
            "battle": {
                "numRounds": SIMS_PER_RUN,
                "gunCoolingRate": 0.1,
                "rules": {"inactivityTime": 450, "hideEnemyNames": True},
            },
            "battleField": {"width": 800, "height": 600},
        }
        user_battle_config = self.game_config.get("battle", {})

        def merge_dicts(default, user):
            for key, value in user.items():
                if isinstance(value, dict) and key in default:
                    merge_dicts(default[key], value)
                else:
                    default[key] = value

        merge_dicts(default_battle_config, user_battle_config)

        # Turn battle config dict into strings
        battle_lines = ["#Battle Properties"]

        def dict_to_lines(d, prefix=""):
            for key, value in d.items():
                if isinstance(value, dict):
                    dict_to_lines(value, prefix + key + ".")
                else:
                    battle_lines.append(f"robocode.{prefix}{key}={value}")

        dict_to_lines(default_battle_config)
        return "\n".join(battle_lines)

    def _run_single_simulation(self, agents: list[Player], idx: int, cmd: str) -> str:
        rc_results = self.log_env / f"results_{idx}.txt"
        rc_record = self.log_env / f"record_{idx}.xml"
        cmd = f"{cmd} -results {rc_results}"
        if random.random() < self.game_config.get("record_ratio", 1):
            # Only record a fraction of simulations to save space
            cmd = f"{cmd} -recordXML {rc_record}"
        try:
            output = self.environment.execute(cmd, timeout=120)
        except subprocess.TimeoutExpired:
            self.logger.warning(f"RoboCode simulation {idx} timed out: {cmd}")
            return ""
        if output["returncode"] != 0:
            self.logger.warning(
                f"RoboCode simulation {idx} failed with exit code {output['returncode']}:\n{output['output']}"
            )
        return output["output"]

    def execute_round(self, agents: list[Player]):
        for agent in agents:
            # Copy the agent codebase into the game codebase and compile it
            for cmd in [
                f"mkdir -p robots/{agent.name}",
                f"cp -r /{agent.name}/robots/custom/* robots/{agent.name}/",
                f"find robots/{agent.name}/ -name '*.java' -exec sed -i 's/custom/{agent.name}/g' {{}} +",
                f'javac -cp "libs/robocode.jar" robots/{agent.name}/*.java',
            ]:
                self.environment.execute(cmd)

        # Create .battle file
        selected_robots = ",".join([f"{agent.name}.{RC_FILE.stem}*" for agent in agents])
        # Use timestamp for unique battle file name since rounds are managed by tournament
        battle_file = f"{self.game_id}-battle{int(time.time())}.battle"
        battle_content = f"""#Battle Properties
{self._get_battle_config()}
robocode.battle.selectedRobots={selected_robots}
"""
        create_file_in_container(self.environment, content=battle_content, dest_path=f"battles/{battle_file}")

        # Run battle with results output to file
        cmd = f"{self.run_cmd_round} -battle {battle_file}"
        self.logger.info(f"Running game: {cmd}")
        with ThreadPoolExecutor(5) as executor:
            # Submit all simulations to the thread pool
            futures = [
                executor.submit(self._run_single_simulation, agents, idx, cmd)
                for idx in range(self.game_config.get("sims_per_round", 100) // SIMS_PER_RUN)
            ]

            # Collect results as they complete
            for future in tqdm(as_completed(futures), total=len(futures)):
                future.result()

    def get_results(self, agents: list[Player], round_num: int, stats: RoundStats):
        scores = defaultdict(int)
        for idx in range(self.game_config.get("sims_per_round", 100) // SIMS_PER_RUN):
            with open(self.log_round(round_num) / f"results_{idx}.txt") as f:
                result_output = f.read()
            lines = result_output.strip().split("\n")

            for line in lines:
                line = line.strip()
                if not re.match(r"^\d", line):
                    continue
                match = re.search(r"(\d+)\S+\:\s(\S+)\s+(\d+)", line)
                if match:
                    player = match.group(2).rsplit(".", 1)[0]
                    scores[player] += int(match.group(3))

        stats.winner = max(scores, key=scores.get)
        stats.scores = scores
        for player, score in scores.items():
            stats.player_stats[player].score = score

    def validate_code(self, agent: Player) -> tuple[bool, str | None]:
        if "robots" not in agent.environment.execute("ls")["output"]:
            return False, "There should be a `robots/` directory"
        if "custom" not in agent.environment.execute("ls robots")["output"]:
            return False, "There should be a `robots/custom/` directory"
        if str(RC_FILE) not in agent.environment.execute("ls robots/custom")["output"]:
            return False, (
                f"There should be a `robots/custom/{RC_FILE}` file. "
                f"You can include additional files, but the primary tank logic must be in `robots/custom/{RC_FILE}`"
            )
        response = agent.environment.execute('javac -cp "libs/robocode.jar" robots/custom/*.java')
        if response["returncode"] != 0:
            return False, f"Compilation error:\n{response['output']}"
        if f"{RC_FILE.stem}.class" not in agent.environment.execute("ls robots/custom")["output"]:
            return False, f"`{RC_FILE.stem}.class` not found after compilation"
        return True, None
