import json
import shlex
import subprocess

from codeclash.agents.player import Player
from codeclash.arenas.arena import CodeArena, RoundStats
from codeclash.constants import RESULT_TIE
from codeclash.utils.environment import assert_zero_exit_code

RESULTS_JSON = "scml_results.json"
CRASH_SCORE = -1_000_000.0


class SCMLOneShotArena(CodeArena):
    name: str = "SCML"
    submission: str = "scml_agent.py"
    description: str = """SCML OneShot is a supply-chain negotiation simulator based on the ANAC Supply Chain Management League.

Your bot is a Python file named `scml_agent.py` that defines a function named `decide`.
The trusted runtime owns the SCML agent object and passes plain decision observations to your code:

    def decide(observation):
        return {}

Each round runs several two-process SCML2024 OneShot worlds. Your policy controls trusted SCML
wrapper agents that negotiate with the other submitted policies to buy and sell goods in a simulated
supply chain. The objective is to maximize profit. The arena score is your average SCML score across
all worlds in the round.
"""
    default_args: dict = {
        "sims_per_round": 3,
        "n_steps": 10,
        "n_lines": 2,
        "decision_timeout": 3.0,
        "max_policy_errors": 8,
        "validation_timeout": 10,
        "timeout": 180,
    }

    def _game_arg(self, key: str):
        return getattr(self, "game_config", {}).get(key, self.default_args[key])

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

        validation_timeout = int(self._game_arg("validation_timeout"))
        try:
            import_check = agent.environment.execute(
                "python - <<'PY'\n"
                "import importlib.util\n"
                f"spec = importlib.util.spec_from_file_location('submission_agent', {self.submission!r})\n"
                "module = importlib.util.module_from_spec(spec)\n"
                "spec.loader.exec_module(module)\n"
                "assert hasattr(module, 'decide'), 'decide function not found'\n"
                "assert callable(module.decide), 'decide must be callable'\n"
                "result = module.decide({'event': 'validate', 'awi': {}, 'state': {}, 'nmi': {}})\n"
                "assert result is None or isinstance(result, dict), 'decide must return a dictionary or None'\n"
                "PY",
                timeout=validation_timeout,
            )
        except subprocess.TimeoutExpired:
            return False, f"`decide` validation exceeded {validation_timeout}s timeout"
        if import_check["returncode"] != 0:
            return False, f"Could not import or call `decide` from `{self.submission}`:\n{import_check['output']}"

        return True, None

    def execute_round(self, agents: list[Player]) -> None:
        agent_args = []
        for agent in agents:
            agent_args.extend(["--agent", f"{agent.name}=/{agent.name}/{self.submission}"])

        cmd = [
            "python",
            "run_scml.py",
            "--sims",
            str(self._game_arg("sims_per_round")),
            "--steps",
            str(self._game_arg("n_steps")),
            "--lines",
            str(self._game_arg("n_lines")),
            "--decision-timeout",
            str(self._game_arg("decision_timeout")),
            "--max-policy-errors",
            str(self._game_arg("max_policy_errors")),
            "--output",
            str(self.log_env / RESULTS_JSON),
            *agent_args,
        ]
        full_cmd = " ".join(shlex.quote(part) for part in cmd)
        self.logger.info(f"Running game: {full_cmd}")
        try:
            response = self.environment.execute(full_cmd, timeout=int(self._game_arg("timeout")))
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("SCML round timed out") from exc
        assert_zero_exit_code(response, logger=self.logger)

    def get_results(self, agents: list[Player], round_num: int, stats: RoundStats):
        result_file = self.log_round(round_num) / RESULTS_JSON
        if not result_file.exists():
            self.logger.error(f"Missing result file: {result_file}")
            stats.winner = RESULT_TIE
            for agent in agents:
                stats.scores[agent.name] = CRASH_SCORE
                stats.player_stats[agent.name].score = CRASH_SCORE
                stats.details.append(
                    json.dumps(
                        {
                            "player": agent.name,
                            "score": CRASH_SCORE,
                            "status": "error",
                            "error": f"missing SCML result file: {result_file}",
                        },
                        sort_keys=True,
                    )
                )
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
