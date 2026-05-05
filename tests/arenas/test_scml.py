import json

from codeclash.arenas.arena import RoundStats
from codeclash.arenas.scml.scml import SCMLOneShotArena
from codeclash.constants import RESULT_TIE

from .conftest import MockPlayer


class TestSCMLValidation:
    def test_valid_agent(self, mock_player_factory):
        arena = SCMLOneShotArena.__new__(SCMLOneShotArena)
        arena.submission = "scml_agent.py"
        player = mock_player_factory(
            name="Alice",
            files={"scml_agent.py": "class MyAgent:\n    pass\n"},
            command_outputs={
                "test -f scml_agent.py && echo exists": {"output": "exists\n", "returncode": 0},
                "cat scml_agent.py": {"output": "class MyAgent:\n    pass\n", "returncode": 0},
                "python -m py_compile scml_agent.py": {"output": "", "returncode": 0},
                "python - <<'PY'": {"output": "", "returncode": 0},
            },
        )

        valid, error = arena.validate_code(player)

        assert valid is True
        assert error is None

    def test_missing_myagent(self, mock_player_factory):
        arena = SCMLOneShotArena.__new__(SCMLOneShotArena)
        arena.submission = "scml_agent.py"
        player = mock_player_factory(
            name="Alice",
            files={"scml_agent.py": "class OtherAgent:\n    pass\n"},
            command_outputs={
                "test -f scml_agent.py && echo exists": {"output": "exists\n", "returncode": 0},
                "cat scml_agent.py": {"output": "class OtherAgent:\n    pass\n", "returncode": 0},
                "python -m py_compile scml_agent.py": {"output": "", "returncode": 0},
                "python - <<'PY'": {"output": "MyAgent class not found", "returncode": 1},
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
            files={"scml_agent.py": "class MyAgent:\n    pass\n"},
            command_outputs={
                "test -f scml_agent.py && echo exists": {"output": "exists\n", "returncode": 0},
                "cat scml_agent.py": {"output": "class MyAgent:\n    pass\n", "returncode": 0},
                "python -m py_compile scml_agent.py": {"output": "", "returncode": 0},
                "python - <<'PY'": {"output": "ImportError", "returncode": 1},
            },
        )

        valid, error = arena.validate_code(player)

        assert valid is False
        assert "Could not import" in error


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
