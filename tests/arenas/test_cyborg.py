import json
import subprocess
from pathlib import Path

from codeclash.arenas.arena import RoundStats
from codeclash.arenas.cyborg.cyborg import CRASH_SCORE, CybORGArena
from codeclash.constants import RESULT_TIE

from .conftest import MockEnvironment, MockPlayer


class TestCybORGValidation:
    def test_valid_agent(self, mock_player_factory):
        arena = CybORGArena.__new__(CybORGArena)
        arena.submission = "cyborg_agent.py"
        player = mock_player_factory(
            name="Alice",
            files={"cyborg_agent.py": "def decide(observation, action_space):\n    return 0\n"},
            command_outputs={
                "test -f cyborg_agent.py && echo exists": {"output": "exists\n", "returncode": 0},
                "cat cyborg_agent.py": {
                    "output": "def decide(observation, action_space):\n    return 0\n",
                    "returncode": 0,
                },
                "python -m py_compile cyborg_agent.py": {"output": "", "returncode": 0},
                "python - <<'PY'": {"output": "", "returncode": 0},
            },
        )

        valid, error = arena.validate_code(player)

        assert valid is True
        assert error is None

    def test_missing_decide(self, mock_player_factory):
        arena = CybORGArena.__new__(CybORGArena)
        arena.submission = "cyborg_agent.py"
        player = mock_player_factory(
            name="Alice",
            files={"cyborg_agent.py": "class OtherAgent:\n    pass\n"},
            command_outputs={
                "test -f cyborg_agent.py && echo exists": {"output": "exists\n", "returncode": 0},
                "cat cyborg_agent.py": {"output": "class OtherAgent:\n    pass\n", "returncode": 0},
                "python -m py_compile cyborg_agent.py": {"output": "", "returncode": 0},
                "python - <<'PY'": {"output": "decide function not found", "returncode": 1},
            },
        )

        valid, error = arena.validate_code(player)

        assert valid is False
        assert "Could not import" in error

    def test_import_failure(self, mock_player_factory):
        arena = CybORGArena.__new__(CybORGArena)
        arena.submission = "cyborg_agent.py"
        player = mock_player_factory(
            name="Alice",
            files={"cyborg_agent.py": "def decide(observation, action_space):\n    raise ImportError('boom')\n"},
            command_outputs={
                "test -f cyborg_agent.py && echo exists": {"output": "exists\n", "returncode": 0},
                "cat cyborg_agent.py": {
                    "output": "def decide(observation, action_space):\n    raise ImportError('boom')\n",
                    "returncode": 0,
                },
                "python -m py_compile cyborg_agent.py": {"output": "", "returncode": 0},
                "python - <<'PY'": {"output": "ImportError", "returncode": 1},
            },
        )

        valid, error = arena.validate_code(player)

        assert valid is False
        assert "Could not import" in error

    def test_validation_calls_decide_with_plain_protocol(self, mock_player_factory):
        arena = CybORGArena.__new__(CybORGArena)
        arena.submission = "cyborg_agent.py"
        player = mock_player_factory(
            name="Alice",
            files={"cyborg_agent.py": "def decide(observation, action_space):\n    return 0\n"},
            command_outputs={
                "test -f cyborg_agent.py && echo exists": {"output": "exists\n", "returncode": 0},
                "cat cyborg_agent.py": {
                    "output": "def decide(observation, action_space):\n    return 0\n",
                    "returncode": 0,
                },
                "python -m py_compile cyborg_agent.py": {"output": "", "returncode": 0},
            },
        )

        valid, error = arena.validate_code(player)

        import_command = player.environment._executed_commands[-1]
        assert valid is True
        assert error is None
        assert "module.decide([0, 1, 0], {'type': 'discrete', 'n': 11})" in import_command
        assert "BaseAgent" not in import_command

    def test_validation_rejects_bad_decide_return_type(self, mock_player_factory):
        arena = CybORGArena.__new__(CybORGArena)
        arena.submission = "cyborg_agent.py"
        player = mock_player_factory(
            name="Alice",
            files={"cyborg_agent.py": "def decide(observation, action_space):\n    return 'bad'\n"},
            command_outputs={
                "test -f cyborg_agent.py && echo exists": {"output": "exists\n", "returncode": 0},
                "cat cyborg_agent.py": {
                    "output": "def decide(observation, action_space):\n    return 'bad'\n",
                    "returncode": 0,
                },
                "python -m py_compile cyborg_agent.py": {"output": "", "returncode": 0},
                "python - <<'PY'": {
                    "output": "decide must return an integer action or None",
                    "returncode": 1,
                },
            },
        )

        valid, error = arena.validate_code(player)

        assert valid is False
        assert "Could not import or call `decide`" in error
        assert "integer action" in error

    def test_validation_rejects_decide_timeout(self):
        class TimeoutEnvironment(MockEnvironment):
            def execute(self, cmd: str, cwd: str | None = None, timeout: int | None = None):
                if cmd.startswith("python - <<'PY'"):
                    raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)
                return super().execute(cmd, cwd=cwd, timeout=timeout)

        arena = CybORGArena.__new__(CybORGArena)
        arena.submission = "cyborg_agent.py"
        player = MockPlayer(
            "Alice",
            TimeoutEnvironment(files={"cyborg_agent.py": "def decide(observation, action_space):\n    return 0\n"}),
        )

        valid, error = arena.validate_code(player)

        assert valid is False
        assert "`decide` validation exceeded 10s timeout" in error


class TestCybORGResults:
    def test_parse_winner(self, tmp_log_dir):
        arena = CybORGArena.__new__(CybORGArena)
        arena.log_local = tmp_log_dir
        arena.logger = type("Logger", (), {"error": lambda self, msg: None})()
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)
        (round_dir / "cyborg_results.json").write_text(
            json.dumps(
                {
                    "average_scores": {"Alice": -10.25, "Bob": -12.75},
                    "details": ['{"episode": 0, "player": "Alice", "score": -10.25}'],
                }
            )
        )

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, 1, stats)

        assert stats.winner == "Alice"
        assert stats.scores == {"Alice": -10.25, "Bob": -12.75}
        assert stats.player_stats["Alice"].score == -10.25
        assert stats.details == ['{"episode": 0, "player": "Alice", "score": -10.25}']

    def test_parse_tie(self, tmp_log_dir):
        arena = CybORGArena.__new__(CybORGArena)
        arena.log_local = tmp_log_dir
        arena.logger = type("Logger", (), {"error": lambda self, msg: None})()
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)
        (round_dir / "cyborg_results.json").write_text(json.dumps({"average_scores": {"Alice": -1, "Bob": -1}}))

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, 1, stats)

        assert stats.winner == RESULT_TIE
        assert stats.scores == {"Alice": -1.0, "Bob": -1.0}


class TestCybORGExecution:
    def test_execute_round_uses_nested_game_args(self):
        arena = CybORGArena.__new__(CybORGArena)
        arena.submission = "cyborg_agent.py"
        arena.config = {
            "game": {
                "sims_per_round": 5,
                "args": {
                    "steps_per_episode": 11,
                    "num_drones": 13,
                    "decision_timeout": 2.5,
                    "timeout": 17,
                },
            }
        }
        arena.log_env = Path("/logs")
        arena.logger = type("Logger", (), {"info": lambda self, msg: None, "error": lambda self, msg: None})()

        class CapturingEnvironment(MockEnvironment):
            def __init__(self):
                super().__init__()
                self.timeout = None

            def execute(self, cmd, cwd=None, timeout=None):
                self._executed_commands.append(cmd)
                self.timeout = timeout
                return {"output": "", "returncode": 0}

        arena.environment = CapturingEnvironment()

        arena.execute_round([MockPlayer("Alice"), MockPlayer("Bob")])

        cmd = arena.environment._executed_commands[0]
        assert "--episodes 5" in cmd
        assert "--steps 11" in cmd
        assert "--drones 13" in cmd
        assert "--decision-timeout 2.5" in cmd
        assert "--output /logs/cyborg_results.json" in cmd
        assert "--agent Alice=/Alice/cyborg_agent.py" in cmd
        assert "--agent Bob=/Bob/cyborg_agent.py" in cmd
        assert arena.environment.timeout == 17

    def test_execute_round_allows_episode_override(self):
        arena = CybORGArena.__new__(CybORGArena)
        arena.submission = "cyborg_agent.py"
        arena.config = {"game": {"sims_per_round": 5, "args": {"episodes_per_round": 7}}}
        arena.log_env = Path("/logs")
        arena.logger = type("Logger", (), {"info": lambda self, msg: None, "error": lambda self, msg: None})()

        class CapturingEnvironment(MockEnvironment):
            def execute(self, cmd, cwd=None, timeout=None):
                self._executed_commands.append(cmd)
                return {"output": "", "returncode": 0}

        arena.environment = CapturingEnvironment()

        arena.execute_round([MockPlayer("Alice")])

        assert "--episodes 7" in arena.environment._executed_commands[0]

    def test_missing_results_file_penalizes_all_players(self, tmp_log_dir):
        arena = CybORGArena.__new__(CybORGArena)
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
        assert "missing CybORG result file" in stats.details[0]
