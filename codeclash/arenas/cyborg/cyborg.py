import json
import shlex
import subprocess

from codeclash.agents.player import Player
from codeclash.arenas.arena import CodeArena, RoundStats
from codeclash.constants import RESULT_TIE
from codeclash.utils.environment import assert_zero_exit_code

RESULTS_JSON = "cyborg_results.json"


class CybORGArena(CodeArena):
    name: str = "CybORG"
    submission: str = "cyborg_agent.py"
    description: str = """CybORG is a simulated cyber-defense arena based on the CAGE Challenge 3 DroneSwarm scenario.

Your bot is a Python file named `cyborg_agent.py` that defines a class named `MyAgent`.
`MyAgent` should inherit from a CybORG BaseAgent-compatible class, for example:

    from CybORG.Agents import RandomAgent

    class MyAgent(RandomAgent):
        ...

Each round evaluates every submitted agent independently on the same seeded DroneSwarm episodes.
Your agent controls the blue-team drone agents through CybORG's simulated PettingZoo interface.
The objective is to maximize average episode reward. This arena uses CybORG simulation only and does
    not run real exploit tools or interact with external networks.
    """
    default_args: dict = {
        "steps_per_episode": 30,
        "num_drones": 18,
        "timeout": 240,
    }

    def _game_arg(self, key: str):
        return self.game_config.get("args", {}).get(key, self.default_args[key])

    def _episodes_per_round(self) -> int:
        return int(self.game_config.get("args", {}).get("episodes_per_round", self.game_config["sims_per_round"]))

    def validate_code(self, agent: Player) -> tuple[bool, str | None]:
        quoted_submission = shlex.quote(self.submission)
        file_check = agent.environment.execute(f"test -f {quoted_submission} && echo exists")
        if "exists" not in file_check["output"]:
            return False, f"Submission file `{self.submission}` not found in the workspace root"

        content = agent.environment.execute(f"cat {quoted_submission}")["output"]
        if not content.strip():
            return False, f"`{self.submission}` is empty"

        syntax_check = agent.environment.execute(f"python -m py_compile {quoted_submission}")
        if syntax_check["returncode"] != 0:
            return False, f"Python syntax error in `{self.submission}`:\n{syntax_check['output']}"

        import_check = agent.environment.execute(
            "python - <<'PY'\n"
            "import importlib.util\n"
            f"spec = importlib.util.spec_from_file_location('submission_agent', {self.submission!r})\n"
            "module = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(module)\n"
            "assert hasattr(module, 'MyAgent'), 'MyAgent class not found'\n"
            "from CybORG.Agents import BaseAgent\n"
            "assert issubclass(module.MyAgent, BaseAgent), 'MyAgent must inherit from a CybORG BaseAgent class'\n"
            "def make_agent(agent_class, agent_name):\n"
            "    try:\n"
            "        return agent_class(name=agent_name)\n"
            "    except TypeError:\n"
            "        try:\n"
            "            return agent_class(agent_name)\n"
            "        except TypeError:\n"
            "            try:\n"
            "                return agent_class()\n"
            "            except TypeError as final_error:\n"
            "                raise TypeError(\n"
            "                    'MyAgent could not be constructed with the CybORG runtime constructor fallbacks'\n"
            "                ) from final_error\n"
            "make_agent(module.MyAgent, 'validation-agent')\n"
            "PY"
        )
        if import_check["returncode"] != 0:
            return False, f"Could not import `MyAgent` from `{self.submission}`:\n{import_check['output']}"

        return True, None

    def execute_round(self, agents: list[Player]) -> None:
        agent_args = []
        for agent in agents:
            agent_args.extend(["--agent", f"{agent.name}=/{agent.name}/{self.submission}"])

        cmd = [
            "python",
            "run_cyborg.py",
            "--episodes",
            str(self._episodes_per_round()),
            "--steps",
            str(self._game_arg("steps_per_episode")),
            "--drones",
            str(self._game_arg("num_drones")),
            "--output",
            str(self.log_env / RESULTS_JSON),
            *agent_args,
        ]
        full_cmd = " ".join(shlex.quote(part) for part in cmd)
        self.logger.info(f"Running game: {full_cmd}")
        try:
            response = self.environment.execute(full_cmd, timeout=int(self._game_arg("timeout")))
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("CybORG round timed out") from exc
        assert_zero_exit_code(response, logger=self.logger)

    def get_results(self, agents: list[Player], round_num: int, stats: RoundStats):
        result_file = self.log_round(round_num) / RESULTS_JSON
        if not result_file.exists():
            self.logger.error(f"Missing result file: {result_file}")
            stats.winner = RESULT_TIE
            for agent in agents:
                stats.scores[agent.name] = 0.0
                stats.player_stats[agent.name].score = 0.0
            return

        with open(result_file) as f:
            result = json.load(f)

        scores = {agent.name: 0.0 for agent in agents}
        for player, score in result.get("average_scores", {}).items():
            if player in scores:
                scores[player] = float(score)

        stats.scores = scores
        stats.details = result.get("details", [])
        for player, score in scores.items():
            stats.player_stats[player].score = score

        if not scores:
            stats.winner = RESULT_TIE
            return

        top_score = max(scores.values())
        winners = [player for player, score in scores.items() if score == top_score]
        stats.winner = winners[0] if len(winners) == 1 else RESULT_TIE
