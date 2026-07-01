import importlib.util
import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

from codeclash.arenas.abides.abides import CRASH_SCORE, ABIDESArena
from codeclash.arenas.arena import RoundStats
from codeclash.constants import RESULT_TIE

from .conftest import MockEnvironment, MockPlayer


def load_runtime_module(monkeypatch):
    class FakeTradingAgent:
        pass

    fake_modules = {
        "agent": types.ModuleType("agent"),
        "agent.ExchangeAgent": types.ModuleType("agent.ExchangeAgent"),
        "agent.market_makers": types.ModuleType("agent.market_makers"),
        "agent.market_makers.MarketMakerAgent": types.ModuleType("agent.market_makers.MarketMakerAgent"),
        "agent.TradingAgent": types.ModuleType("agent.TradingAgent"),
        "agent.ZeroIntelligenceAgent": types.ModuleType("agent.ZeroIntelligenceAgent"),
        "Kernel": types.ModuleType("Kernel"),
        "util": types.ModuleType("util"),
        "util.oracle": types.ModuleType("util.oracle"),
        "util.oracle.SparseMeanRevertingOracle": types.ModuleType("util.oracle.SparseMeanRevertingOracle"),
        "util.order": types.ModuleType("util.order"),
    }
    fake_modules["agent.ExchangeAgent"].ExchangeAgent = type("ExchangeAgent", (), {})
    fake_modules["agent.market_makers.MarketMakerAgent"].MarketMakerAgent = type("MarketMakerAgent", (), {})
    fake_modules["agent.TradingAgent"].TradingAgent = FakeTradingAgent
    fake_modules["agent.ZeroIntelligenceAgent"].ZeroIntelligenceAgent = type("ZeroIntelligenceAgent", (), {})
    fake_modules["Kernel"].Kernel = type("Kernel", (), {})
    fake_modules["util"].util = types.SimpleNamespace(silent_mode=False)
    fake_modules["util.oracle.SparseMeanRevertingOracle"].SparseMeanRevertingOracle = type(
        "SparseMeanRevertingOracle", (), {}
    )
    fake_modules["util.order"].LimitOrder = type("LimitOrder", (), {"silent_mode": False})
    for name, module in fake_modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    runtime_path = Path(__file__).parents[2] / "codeclash/arenas/abides/runtime/run_abides.py"
    spec = importlib.util.spec_from_file_location("run_abides_test", runtime_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestABIDESValidation:
    def test_valid_agent(self, mock_player_factory):
        arena = ABIDESArena.__new__(ABIDESArena)
        arena.submission = "abides_agent.py"
        arena.config = {"game": {"args": {"validation_timeout": 3}}}
        player = mock_player_factory(
            name="Alice",
            files={"abides_agent.py": "def decide(observation):\n    return []\n"},
            command_outputs={
                "test -f abides_agent.py && echo exists": {"output": "exists\n", "returncode": 0},
                "cat abides_agent.py": {
                    "output": "def decide(observation):\n    return []\n",
                    "returncode": 0,
                },
                "python -m py_compile abides_agent.py": {"output": "", "returncode": 0},
                "python - <<'PY'": {"output": "", "returncode": 0},
            },
        )

        valid, error = arena.validate_code(player)

        assert valid is True
        assert error is None
        import_command = next(cmd for cmd in player.environment._executed_commands if cmd.startswith("python - <<'PY'"))
        assert "module.decide(observation)" in import_command
        assert "TradingAgent" not in import_command

    def test_validation_import_uses_timeout(self, mock_player_factory):
        arena = ABIDESArena.__new__(ABIDESArena)
        arena.submission = "abides_agent.py"
        arena.config = {"game": {"args": {"validation_timeout": 7}}}

        class CapturingEnvironment(MockEnvironment):
            def __init__(self):
                super().__init__(
                    files={"abides_agent.py": "def decide(observation):\n    return []\n"},
                    command_outputs={
                        "python -m py_compile abides_agent.py": {"output": "", "returncode": 0},
                        "python - <<'PY'": {"output": "", "returncode": 0},
                    },
                )
                self.timeouts = []

            def execute(self, cmd, cwd=None, timeout=None):
                self.timeouts.append((cmd, timeout))
                return super().execute(cmd, cwd=cwd, timeout=timeout)

        player = MockPlayer("Alice", CapturingEnvironment())

        valid, error = arena.validate_code(player)

        assert valid is True
        assert error is None
        import_timeout = next(
            timeout for cmd, timeout in player.environment.timeouts if cmd.startswith("python - <<'PY'")
        )
        assert import_timeout == 7

    def test_missing_decide(self, mock_player_factory):
        arena = ABIDESArena.__new__(ABIDESArena)
        arena.submission = "abides_agent.py"
        arena.config = {"game": {}}
        player = mock_player_factory(
            name="Alice",
            files={"abides_agent.py": "class OtherAgent:\n    pass\n"},
            command_outputs={
                "test -f abides_agent.py && echo exists": {"output": "exists\n", "returncode": 0},
                "cat abides_agent.py": {"output": "class OtherAgent:\n    pass\n", "returncode": 0},
                "python -m py_compile abides_agent.py": {"output": "", "returncode": 0},
                "python - <<'PY'": {"output": "decide function not found", "returncode": 1},
            },
        )

        valid, error = arena.validate_code(player)

        assert valid is False
        assert "Could not import or call" in error

    def test_import_failure(self, mock_player_factory):
        arena = ABIDESArena.__new__(ABIDESArena)
        arena.submission = "abides_agent.py"
        arena.config = {"game": {}}
        player = mock_player_factory(
            name="Alice",
            files={"abides_agent.py": "def decide(observation):\n    raise ImportError('boom')\n"},
            command_outputs={
                "test -f abides_agent.py && echo exists": {"output": "exists\n", "returncode": 0},
                "cat abides_agent.py": {
                    "output": "def decide(observation):\n    raise ImportError('boom')\n",
                    "returncode": 0,
                },
                "python -m py_compile abides_agent.py": {"output": "", "returncode": 0},
                "python - <<'PY'": {"output": "ImportError", "returncode": 1},
            },
        )

        valid, error = arena.validate_code(player)

        assert valid is False
        assert "Could not import or call" in error

    def test_validation_timeout_invalidates_submission(self):
        arena = ABIDESArena.__new__(ABIDESArena)
        arena.submission = "abides_agent.py"
        arena.config = {"game": {"args": {"validation_timeout": 5}}}

        class TimeoutEnvironment(MockEnvironment):
            def execute(self, cmd, cwd=None, timeout=None):
                if cmd.startswith("python - <<'PY'"):
                    raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)
                return super().execute(cmd, cwd=cwd, timeout=timeout)

        player = MockPlayer(
            "Alice",
            TimeoutEnvironment(files={"abides_agent.py": "def decide(observation):\n    return []\n"}),
        )

        valid, error = arena.validate_code(player)

        assert valid is False
        assert "`decide` validation exceeded 5s timeout" in error


class TestABIDESResults:
    def test_parse_winner(self, tmp_log_dir):
        arena = ABIDESArena.__new__(ABIDESArena)
        arena.log_local = tmp_log_dir
        arena.logger = type("Logger", (), {"error": lambda self, msg: None})()
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)
        (round_dir / "abides_results.json").write_text(
            json.dumps(
                {
                    "average_scores": {"Alice": 125.0, "Bob": 75.0},
                    "details": ['{"sim": 0, "player": "Alice", "score": 125.0}'],
                }
            )
        )

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, 1, stats)

        assert stats.winner == "Alice"
        assert stats.scores == {"Alice": 125.0, "Bob": 75.0}
        assert stats.player_stats["Alice"].score == 125.0
        assert stats.details == ['{"sim": 0, "player": "Alice", "score": 125.0}']

    def test_parse_tie(self, tmp_log_dir):
        arena = ABIDESArena.__new__(ABIDESArena)
        arena.log_local = tmp_log_dir
        arena.logger = type("Logger", (), {"error": lambda self, msg: None})()
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)
        (round_dir / "abides_results.json").write_text(json.dumps({"average_scores": {"Alice": 1, "Bob": 1}}))

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, 1, stats)

        assert stats.winner == RESULT_TIE
        assert stats.scores == {"Alice": 1.0, "Bob": 1.0}

    def test_missing_score_is_penalized(self, tmp_log_dir):
        arena = ABIDESArena.__new__(ABIDESArena)
        arena.log_local = tmp_log_dir
        arena.logger = type("Logger", (), {"error": lambda self, msg: None})()
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)
        (round_dir / "abides_results.json").write_text(json.dumps({"average_scores": {"Bob": -5.0}}))

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, 1, stats)

        assert stats.winner == "Bob"
        assert stats.scores == {"Alice": CRASH_SCORE, "Bob": -5.0}
        assert "missing ABIDES score" in stats.details[0]

    def test_missing_results_file_penalizes_all_players(self, tmp_log_dir):
        arena = ABIDESArena.__new__(ABIDESArena)
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
        assert "missing ABIDES result file" in stats.details[0]


class TestABIDESExecution:
    def test_execute_round_uses_nested_game_args(self):
        arena = ABIDESArena.__new__(ABIDESArena)
        arena.submission = "abides_agent.py"
        arena.config = {
            "game": {
                "sims_per_round": 5,
                "args": {
                    "market_minutes": 11,
                    "background_agents": 13,
                    "decision_timeout": 2.5,
                    "player_timeout": 19,
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
        assert "--market-minutes 11" in cmd
        assert "--background-agents 13" in cmd
        assert "--decision-timeout 2.5" in cmd
        assert "--player-timeout 19" in cmd
        assert "--output /logs/abides_results.json" in cmd
        assert "--agent Alice=/Alice/abides_agent.py" in cmd
        assert "--agent Bob=/Bob/abides_agent.py" in cmd
        assert arena.environment.timeout == 17


class TestABIDESRuntimeProtocol:
    def test_normalize_order_intents_rejects_boolean_numeric_fields(self, monkeypatch):
        runtime = load_runtime_module(monkeypatch)

        with pytest.raises(ValueError, match="quantity"):
            runtime.normalize_order_intents({"side": "buy", "quantity": True, "limit_price": 100_000})

        with pytest.raises(ValueError, match="limit_price"):
            runtime.normalize_order_intents({"side": "buy", "quantity": 1, "limit_price": False})

    def test_normalize_order_intents_accepts_whole_number_floats_and_clamps(self, monkeypatch):
        runtime = load_runtime_module(monkeypatch)

        assert runtime.normalize_order_intents({"side": "buy", "quantity": 25.0, "limit_price": 2_000_000.0}) == [
            {"side": "buy", "quantity": runtime.MAX_ORDER_QUANTITY, "limit_price": runtime.MAX_LIMIT_PRICE}
        ]

    def test_normalize_order_intents_rejects_non_integral_floats(self, monkeypatch):
        runtime = load_runtime_module(monkeypatch)

        with pytest.raises(ValueError, match="quantity"):
            runtime.normalize_order_intents({"side": "buy", "quantity": 1.5, "limit_price": 100_000})
