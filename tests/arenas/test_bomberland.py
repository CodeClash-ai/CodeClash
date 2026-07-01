import importlib.util
import json
import subprocess
import time
from pathlib import Path

import pytest

from codeclash.arenas import get_arena
from codeclash.arenas.arena import RoundStats
from codeclash.arenas.bomberland.bomberland import CRASH_SCORE, BomberlandArena
from codeclash.constants import RESULT_TIE

from .conftest import MockEnvironment, MockPlayer


def load_runtime_module():
    runtime_path = Path(__file__).parents[2] / "codeclash/arenas/bomberland/runtime/run_bomberland.py"
    spec = importlib.util.spec_from_file_location("run_bomberland_test", runtime_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestBomberlandValidation:
    def test_valid_agent(self, mock_player_factory):
        arena = BomberlandArena.__new__(BomberlandArena)
        arena.submission = "bomberland_agent.py"
        arena.config = {"game": {"name": "Bomberland", "sims_per_round": 1}}
        player = mock_player_factory(
            name="Alice",
            files={"bomberland_agent.py": "def next_actions(game_state):\n    return {}\n"},
            command_outputs={
                "test -f bomberland_agent.py && echo exists": {"output": "exists\n", "returncode": 0},
                "cat bomberland_agent.py": {
                    "output": "def next_actions(game_state):\n    return {}\n",
                    "returncode": 0,
                },
                "python -m py_compile bomberland_agent.py": {"output": "", "returncode": 0},
                "python - <<'PY'": {"output": "", "returncode": 0},
            },
        )

        valid, error = arena.validate_code(player)

        assert valid is True
        assert error is None

    def test_missing_next_actions(self, mock_player_factory):
        arena = BomberlandArena.__new__(BomberlandArena)
        arena.submission = "bomberland_agent.py"
        arena.config = {"game": {"name": "Bomberland", "sims_per_round": 1}}
        player = mock_player_factory(
            name="Alice",
            files={"bomberland_agent.py": "def choose_action(game_state):\n    return {}\n"},
            command_outputs={
                "test -f bomberland_agent.py && echo exists": {"output": "exists\n", "returncode": 0},
                "cat bomberland_agent.py": {
                    "output": "def choose_action(game_state):\n    return {}\n",
                    "returncode": 0,
                },
                "python -m py_compile bomberland_agent.py": {"output": "", "returncode": 0},
                "python - <<'PY'": {"output": "next_actions callable not found", "returncode": 1},
            },
        )

        valid, error = arena.validate_code(player)

        assert valid is False
        assert "Could not import or call" in error

    def test_next_actions_wrong_return_type(self, mock_player_factory):
        arena = BomberlandArena.__new__(BomberlandArena)
        arena.submission = "bomberland_agent.py"
        arena.config = {"game": {"name": "Bomberland", "sims_per_round": 1}}
        player = mock_player_factory(
            name="Alice",
            files={"bomberland_agent.py": "def next_actions(game_state):\n    return []\n"},
            command_outputs={
                "test -f bomberland_agent.py && echo exists": {"output": "exists\n", "returncode": 0},
                "cat bomberland_agent.py": {
                    "output": "def next_actions(game_state):\n    return []\n",
                    "returncode": 0,
                },
                "python -m py_compile bomberland_agent.py": {"output": "", "returncode": 0},
                "python - <<'PY'": {"output": "next_actions must return a dict or None", "returncode": 1},
            },
        )

        valid, error = arena.validate_code(player)

        assert valid is False
        assert "Could not import or call" in error

    def test_import_probe_uses_validation_timeout(self, mock_player_factory):
        arena = BomberlandArena.__new__(BomberlandArena)
        arena.submission = "bomberland_agent.py"
        arena.config = {"game": {"name": "Bomberland", "sims_per_round": 1, "args": {"validation_timeout": 9}}}

        class CapturingEnvironment(MockEnvironment):
            def __init__(self):
                super().__init__(
                    files={"bomberland_agent.py": "def next_actions(game_state):\n    return {}\n"},
                    command_outputs={
                        "python -m py_compile bomberland_agent.py": {"output": "", "returncode": 0},
                        "python - <<'PY'": {"output": "", "returncode": 0},
                    },
                )
                self.timeouts = []

            def execute(self, cmd, cwd=None, timeout=None):
                self.timeouts.append(timeout)
                return super().execute(cmd, cwd=cwd, timeout=timeout)

        player = MockPlayer("Alice", CapturingEnvironment())

        valid, error = arena.validate_code(player)

        assert valid is True
        assert error is None
        assert player.environment.timeouts[-1] == 9

    def test_validation_timeout_invalidates_submission(self):
        arena = BomberlandArena.__new__(BomberlandArena)
        arena.submission = "bomberland_agent.py"
        arena.config = {"game": {"name": "Bomberland", "args": {"validation_timeout": 3}}}

        class TimeoutEnvironment(MockEnvironment):
            def __init__(self):
                super().__init__(
                    files={"bomberland_agent.py": "def next_actions(game_state):\n    return {}\n"},
                    command_outputs={"python -m py_compile bomberland_agent.py": {"output": "", "returncode": 0}},
                )

            def execute(self, cmd, cwd=None, timeout=None):
                if cmd.startswith("python - <<'PY'"):
                    raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)
                return super().execute(cmd, cwd=cwd, timeout=timeout)

        valid, error = arena.validate_code(MockPlayer("Alice", TimeoutEnvironment()))

        assert valid is False
        assert error == "`next_actions` validation exceeded 3s timeout"


class TestBomberlandResults:
    def test_parse_winner(self, tmp_log_dir):
        arena = BomberlandArena.__new__(BomberlandArena)
        arena.log_local = tmp_log_dir
        arena.logger = type("Logger", (), {"error": lambda self, msg: None})()
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)
        (round_dir / "bomberland_results.json").write_text(
            json.dumps(
                {
                    "average_scores": {"Alice": 325.5, "Bob": 300.0},
                    "details": ['{"sim": 0, "winner": "Alice"}'],
                }
            )
        )

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, 1, stats)

        assert stats.winner == "Alice"
        assert stats.scores == {"Alice": 325.5, "Bob": 300.0}
        assert stats.player_stats["Alice"].score == 325.5
        assert stats.details == ['{"sim": 0, "winner": "Alice"}']

    def test_parse_tie(self, tmp_log_dir):
        arena = BomberlandArena.__new__(BomberlandArena)
        arena.log_local = tmp_log_dir
        arena.logger = type("Logger", (), {"error": lambda self, msg: None})()
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)
        (round_dir / "bomberland_results.json").write_text(json.dumps({"average_scores": {"Alice": 10, "Bob": 10}}))

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, 1, stats)

        assert stats.winner == RESULT_TIE
        assert stats.scores == {"Alice": 10.0, "Bob": 10.0}

    def test_missing_player_uses_crash_score(self, tmp_log_dir):
        arena = BomberlandArena.__new__(BomberlandArena)
        arena.log_local = tmp_log_dir
        arena.logger = type("Logger", (), {"error": lambda self, msg: None})()
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)
        (round_dir / "bomberland_results.json").write_text(json.dumps({"average_scores": {"Alice": -5}}))

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, 1, stats)

        assert stats.winner == "Alice"
        assert stats.scores == {"Alice": -5.0, "Bob": CRASH_SCORE}

    def test_missing_result_file_records_crash_details(self, tmp_log_dir):
        arena = BomberlandArena.__new__(BomberlandArena)
        arena.log_local = tmp_log_dir
        arena.logger = type("Logger", (), {"error": lambda self, msg: None})()
        (tmp_log_dir / "rounds" / "1").mkdir(parents=True)

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, 1, stats)

        assert stats.winner == RESULT_TIE
        assert stats.scores == {"Alice": CRASH_SCORE, "Bob": CRASH_SCORE}
        assert len(stats.details) == 2
        detail = json.loads(stats.details[0])
        assert detail["status"] == "error"
        assert detail["score"] == CRASH_SCORE
        assert "missing Bomberland result file" in detail["error"]


class TestBomberlandExecution:
    def test_execute_round_uses_nested_game_args(self):
        arena = BomberlandArena.__new__(BomberlandArena)
        arena.submission = "bomberland_agent.py"
        arena.config = {
            "game": {
                "sims_per_round": 5,
                "args": {
                    "ticks": 11,
                    "width": 13,
                    "height": 15,
                    "unit_count": 2,
                    "agent_timeout": 0.1,
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
        assert "--sims 5" in cmd
        assert "--ticks 11" in cmd
        assert "--width 13" in cmd
        assert "--height 15" in cmd
        assert "--unit-count 2" in cmd
        assert "--agent-timeout 0.1" in cmd
        assert "--output /logs/bomberland_results.json" in cmd
        assert "--agent Alice=/Alice/bomberland_agent.py" in cmd
        assert "--agent Bob=/Bob/bomberland_agent.py" in cmd
        assert arena.environment.timeout == 17


class TestBomberlandRuntime:
    def test_call_agent_times_out_submitted_code(self, tmp_path):
        runtime = load_runtime_module()
        agent_path = tmp_path / "bomberland_agent.py"
        agent_path.write_text(
            "def next_actions(game_state):\n"
            "    try:\n"
            "        while True:\n"
            "            pass\n"
            "    except BaseException:\n"
            "        while True:\n"
            "            pass\n"
        )

        start = time.perf_counter()
        result = runtime.call_agent(str(agent_path), {}, 0.05)
        elapsed = time.perf_counter() - start

        assert result == {"__error__": "Timeout"}
        assert elapsed < 2

    def test_call_agent_supports_sibling_imports(self, tmp_path):
        runtime = load_runtime_module()
        (tmp_path / "helper.py").write_text("ACTION = 'stay'\n")
        agent_path = tmp_path / "bomberland_agent.py"
        agent_path.write_text("from helper import ACTION\n\ndef next_actions(game_state):\n    return {'u0': ACTION}\n")

        result = runtime.call_agent(str(agent_path), {}, 1)

        assert result == {"u0": "stay"}

    def test_malformed_dict_detonate_is_invalid(self):
        runtime = load_runtime_module()

        assert runtime.normalize_action({"type": "detonate", "coordinates": ["bad", 0]}) == ("invalid", None)


def test_bomberland_registered(monkeypatch, minimal_config, tmp_log_dir):
    config = {
        **minimal_config,
        "game": {
            "name": "Bomberland",
            "sims_per_round": 2,
        },
    }

    monkeypatch.setattr(BomberlandArena, "build_image", lambda self: None)
    monkeypatch.setattr(BomberlandArena, "get_environment", lambda self: MockEnvironment())

    arena = get_arena(config, tournament_id="test", local_output_dir=tmp_log_dir)

    assert isinstance(arena, BomberlandArena)


def test_bomberland_rejects_non_two_player_configs(minimal_config, tmp_log_dir):
    config = {
        **minimal_config,
        "game": {
            "name": "Bomberland",
            "sims_per_round": 1,
        },
        "players": [
            {"name": "p1", "agent": "dummy"},
            {"name": "p2", "agent": "dummy"},
            {"name": "p3", "agent": "dummy"},
        ],
    }

    with pytest.raises(ValueError, match="exactly two players"):
        BomberlandArena(config, tournament_id="test", local_output_dir=tmp_log_dir)


def test_bomberland_rejects_odd_sim_counts(minimal_config, tmp_log_dir):
    config = {
        **minimal_config,
        "game": {
            "name": "Bomberland",
            "sims_per_round": 3,
        },
    }

    with pytest.raises(ValueError, match="even sims_per_round"):
        BomberlandArena(config, tournament_id="test", local_output_dir=tmp_log_dir)
