import json
import shlex
import subprocess

from codeclash.agents.player import Player
from codeclash.arenas.arena import CodeArena, RoundStats
from codeclash.constants import RESULT_TIE
from codeclash.utils.environment import assert_zero_exit_code

RESULTS_JSON = "bomberland_results.json"
CRASH_SCORE = -1_000_000.0


class BomberlandArena(CodeArena):
    name: str = "Bomberland"
    submission: str = "bomberland_agent.py"
    description: str = """Bomberland is a Bomberman-style multi-agent arena based on Coder One's Bomberland competition.

Your bot is a Python file named `bomberland_agent.py` that defines a callable named `next_actions`.
The callable receives a game-state dictionary and should return a dictionary mapping unit ids to actions:

    def next_actions(game_state):
        return {"unit_0": "up"}

Valid actions are `up`, `down`, `left`, `right`, `bomb`, `stay`, and `detonate` (to blow up one of
your own bombs early, e.g. the string `"detonate:x,y"` or `{"type": "detonate", "coordinates": [x, y]}`;
bombs also explode automatically after their timer). Each round runs several deterministic seeded
games. Your units move on a destructible grid, place bombs, destroy blocks, damage opposing units,
and score by survival, damage, kills, and block destruction. Bomb blasts (`x` entities) stay active
briefly and damage any unit standing on or moving into them.
"""
    default_args: dict = {
        "sims_per_round": 4,
        "ticks": 80,
        "width": 11,
        "height": 11,
        "unit_count": 3,
        "agent_timeout": 0.25,
        "validation_timeout": 5,
        "timeout": 180,
    }

    def __init__(self, config: dict, **kwargs):
        player_count = len(config.get("players", []))
        if player_count != 2:
            raise ValueError("Bomberland requires exactly two players")
        game_config = config.get("game", {})
        game_args = game_config.get("args", {})
        sims_per_round = int(
            game_args.get("sims_per_round", game_config.get("sims_per_round", self.default_args["sims_per_round"]))
        )
        if sims_per_round % 2 != 0:
            raise ValueError("Bomberland requires an even sims_per_round so both players get paired starting sides")
        super().__init__(config, **kwargs)

    def _game_arg(self, key: str):
        nested_args = self.game_config.get("args", {})
        return nested_args.get(key, self.game_config.get(key, self.default_args[key]))

    def _sims_per_round(self) -> int:
        return int(self._game_arg("sims_per_round"))

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
                "assert hasattr(module, 'next_actions'), 'next_actions callable not found'\n"
                "assert callable(module.next_actions), 'next_actions must be callable'\n"
                "state = {\n"
                "    'connection': {'agent_id': 'Alice'},\n"
                "    'agents': {'Alice': {'unit_ids': ['u0']}},\n"
                "    'unit_state': {'u0': {'agent_id': 'Alice', 'hp': 3, 'coordinates': [1, 1]}},\n"
                "    'entities': [],\n"
                "    'world': {'width': 5, 'height': 5},\n"
                "    'tick': 0,\n"
                "}\n"
                "result = module.next_actions(state)\n"
                "assert result is None or isinstance(result, dict), 'next_actions must return a dict or None'\n"
                "PY",
                timeout=validation_timeout,
            )
        except subprocess.TimeoutExpired:
            return False, f"`next_actions` validation exceeded {validation_timeout}s timeout"
        if import_check["returncode"] != 0:
            return False, f"Could not import or call `next_actions` from `{self.submission}`:\n{import_check['output']}"

        return True, None

    def execute_round(self, agents: list[Player]) -> None:
        agent_args = []
        for agent in agents:
            agent_args.extend(["--agent", f"{agent.name}=/{agent.name}/{self.submission}"])

        cmd = [
            "python",
            "run_bomberland.py",
            "--sims",
            str(self._sims_per_round()),
            "--ticks",
            str(self._game_arg("ticks")),
            "--width",
            str(self._game_arg("width")),
            "--height",
            str(self._game_arg("height")),
            "--unit-count",
            str(self._game_arg("unit_count")),
            "--agent-timeout",
            str(self._game_arg("agent_timeout")),
            "--output",
            str(self.log_env / RESULTS_JSON),
            *agent_args,
        ]
        full_cmd = " ".join(shlex.quote(part) for part in cmd)
        self.logger.info(f"Running game: {full_cmd}")
        try:
            response = self.environment.execute(full_cmd, timeout=int(self._game_arg("timeout")))
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Bomberland round timed out") from exc
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
                            "error": f"missing Bomberland result file: {result_file}",
                        },
                        sort_keys=True,
                    )
                )
            return

        with open(result_file) as f:
            result = json.load(f)

        scores = {agent.name: CRASH_SCORE for agent in agents}
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
