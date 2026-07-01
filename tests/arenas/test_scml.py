import json
import subprocess
from pathlib import Path

from codeclash.arenas.arena import RoundStats
from codeclash.arenas.scml.scml import CRASH_SCORE, SCMLOneShotArena
from codeclash.constants import RESULT_TIE

from .conftest import MockEnvironment, MockPlayer


class TestSCMLValidation:
    def test_valid_agent(self, mock_player_factory):
        arena = SCMLOneShotArena.__new__(SCMLOneShotArena)
        arena.submission = "scml_agent.py"
        player = mock_player_factory(
            name="Alice",
            files={"scml_agent.py": "def decide(observation):\n    return {}\n"},
            command_outputs={
                "test -f scml_agent.py && echo exists": {"output": "exists\n", "returncode": 0},
                "cat scml_agent.py": {"output": "def decide(observation):\n    return {}\n", "returncode": 0},
                "python -m py_compile scml_agent.py": {"output": "", "returncode": 0},
                "python - <<'PY'": {"output": "", "returncode": 0},
            },
        )

        valid, error = arena.validate_code(player)

        assert valid is True
        assert error is None

    def test_missing_decide(self, mock_player_factory):
        arena = SCMLOneShotArena.__new__(SCMLOneShotArena)
        arena.submission = "scml_agent.py"
        player = mock_player_factory(
            name="Alice",
            files={"scml_agent.py": "class OtherAgent:\n    pass\n"},
            command_outputs={
                "test -f scml_agent.py && echo exists": {"output": "exists\n", "returncode": 0},
                "cat scml_agent.py": {"output": "class OtherAgent:\n    pass\n", "returncode": 0},
                "python -m py_compile scml_agent.py": {"output": "", "returncode": 0},
                "python - <<'PY'": {"output": "decide function not found", "returncode": 1},
            },
        )

        valid, error = arena.validate_code(player)

        assert valid is False
        assert "Could not import" in error

    def test_import_failure(self, mock_player_factory):
        arena = SCMLOneShotArena.__new__(SCMLOneShotArena)
        arena.submission = "scml_agent.py"
        player = mock_player_factory(
            name="Alice",
            files={"scml_agent.py": "def decide(observation):\n    raise ImportError('boom')\n"},
            command_outputs={
                "test -f scml_agent.py && echo exists": {"output": "exists\n", "returncode": 0},
                "cat scml_agent.py": {
                    "output": "def decide(observation):\n    raise ImportError('boom')\n",
                    "returncode": 0,
                },
                "python -m py_compile scml_agent.py": {"output": "", "returncode": 0},
                "python - <<'PY'": {"output": "ImportError", "returncode": 1},
            },
        )

        valid, error = arena.validate_code(player)

        assert valid is False
        assert "Could not import" in error

    def test_validation_calls_decide_with_plain_protocol(self, mock_player_factory):
        arena = SCMLOneShotArena.__new__(SCMLOneShotArena)
        arena.submission = "scml_agent.py"
        player = mock_player_factory(
            name="Alice",
            files={"scml_agent.py": "def decide(observation):\n    return {}\n"},
            command_outputs={
                "test -f scml_agent.py && echo exists": {"output": "exists\n", "returncode": 0},
                "cat scml_agent.py": {"output": "def decide(observation):\n    return {}\n", "returncode": 0},
                "python -m py_compile scml_agent.py": {"output": "", "returncode": 0},
                "python - <<'PY'": {"output": "", "returncode": 0},
            },
        )

        valid, error = arena.validate_code(player)

        import_command = player.environment._executed_commands[-1]
        assert valid is True
        assert error is None
        assert "module.decide({'event': 'validate', 'awi': {}, 'state': {}, 'nmi': {}})" in import_command
        assert "OneShotAgent" not in import_command

    def test_validation_rejects_bad_decide_return_type(self, mock_player_factory):
        arena = SCMLOneShotArena.__new__(SCMLOneShotArena)
        arena.submission = "scml_agent.py"
        player = mock_player_factory(
            name="Alice",
            files={"scml_agent.py": "def decide(observation):\n    return 'bad'\n"},
            command_outputs={
                "test -f scml_agent.py && echo exists": {"output": "exists\n", "returncode": 0},
                "cat scml_agent.py": {"output": "def decide(observation):\n    return 'bad'\n", "returncode": 0},
                "python -m py_compile scml_agent.py": {"output": "", "returncode": 0},
                "python - <<'PY'": {"output": "decide must return a dictionary or None", "returncode": 1},
            },
        )

        valid, error = arena.validate_code(player)

        assert valid is False
        assert "Could not import or call `decide`" in error
        assert "dictionary" in error

    def test_validation_rejects_decide_timeout(self):
        class TimeoutEnvironment(MockEnvironment):
            def execute(self, cmd: str, cwd: str | None = None, timeout: int | None = None):
                if cmd.startswith("python - <<'PY'"):
                    raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)
                return super().execute(cmd, cwd=cwd, timeout=timeout)

        arena = SCMLOneShotArena.__new__(SCMLOneShotArena)
        arena.submission = "scml_agent.py"
        player = MockPlayer(
            "Alice",
            TimeoutEnvironment(files={"scml_agent.py": "def decide(observation):\n    return {}\n"}),
        )

        valid, error = arena.validate_code(player)

        assert valid is False
        assert "`decide` validation exceeded 10s timeout" in error


class TestSCMLResults:
    def test_parse_winner(self, tmp_log_dir):
        arena = SCMLOneShotArena.__new__(SCMLOneShotArena)
        arena.log_local = tmp_log_dir
        arena.logger = type("Logger", (), {"error": lambda self, msg: None})()
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)
        (round_dir / "scml_results.json").write_text(
            json.dumps(
                {
                    "average_scores": {"Alice": 1.25, "Bob": 0.75},
                    "details": ['{"sim": 0, "player": "Alice", "score": 1.25}'],
                }
            )
        )

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, 1, stats)

        assert stats.winner == "Alice"
        assert stats.scores == {"Alice": 1.25, "Bob": 0.75}
        assert stats.player_stats["Alice"].score == 1.25
        assert stats.details == ['{"sim": 0, "player": "Alice", "score": 1.25}']

    def test_parse_tie(self, tmp_log_dir):
        arena = SCMLOneShotArena.__new__(SCMLOneShotArena)
        arena.log_local = tmp_log_dir
        arena.logger = type("Logger", (), {"error": lambda self, msg: None})()
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)
        (round_dir / "scml_results.json").write_text(json.dumps({"average_scores": {"Alice": 1, "Bob": 1}}))

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, 1, stats)

        assert stats.winner == RESULT_TIE
        assert stats.scores == {"Alice": 1.0, "Bob": 1.0}

    def test_missing_results_file_penalizes_all_players(self, tmp_log_dir):
        arena = SCMLOneShotArena.__new__(SCMLOneShotArena)
        arena.log_local = tmp_log_dir
        arena.logger = type("Logger", (), {"error": lambda self, msg: None})()

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, 1, stats)

        assert stats.winner == RESULT_TIE
        assert stats.scores == {"Alice": CRASH_SCORE, "Bob": CRASH_SCORE}
        assert stats.player_stats["Alice"].score == CRASH_SCORE
        assert stats.player_stats["Bob"].score == CRASH_SCORE
        assert len(stats.details) == 2
        assert "missing SCML result file" in stats.details[0]


class TestSCMLExecution:
    def test_execute_round_passes_restricted_protocol_args(self):
        arena = SCMLOneShotArena.__new__(SCMLOneShotArena)
        arena.submission = "scml_agent.py"
        arena.log_env = Path("/logs")
        arena.config = {
            "game": {
                "sims_per_round": 5,
                "n_steps": 11,
                "n_lines": 3,
                "decision_timeout": 0.75,
                "max_policy_errors": 4,
                "timeout": 17,
            }
        }
        arena.environment = MockEnvironment()
        arena.logger = type("Logger", (), {"info": lambda self, msg: None})()

        arena.execute_round([MockPlayer("Alice"), MockPlayer("Bob")])

        cmd = arena.environment._executed_commands[0]
        assert "python run_scml.py" in cmd
        assert "--sims 5" in cmd
        assert "--steps 11" in cmd
        assert "--lines 3" in cmd
        assert "--decision-timeout 0.75" in cmd
        assert "--max-policy-errors 4" in cmd
        assert "--output /logs/scml_results.json" in cmd
        assert "--agent Alice=/Alice/scml_agent.py" in cmd
        assert "--agent Bob=/Bob/scml_agent.py" in cmd
