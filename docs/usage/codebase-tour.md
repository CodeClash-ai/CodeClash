# Codebase Tour

This guide helps contributors understand the CodeClash architecture. Whether you're adding a new arena, implementing an agent, or fixing a bug, this tour will orient you to the key modules and extension points.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          main.py                                 │
│                    (CLI entry point)                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    tournaments/pvp.py                            │
│                  (Tournament orchestration)                      │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   arenas/       │  │   agents/       │  │   utils/        │
│  (Game logic)   │  │ (LLM agents)    │  │  (Docker, Git)  │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

## Directory Structure

```
codeclash/
├── __init__.py           # Package init, defines PACKAGE_DIR, CONFIG_DIR
├── constants.py          # Global constants (LOG_DIR, etc.)
│
├── agents/               # AI agent implementations
│   ├── __init__.py       # Agent registry and get_agent()
│   ├── player.py         # Abstract Player base class
│   ├── minisweagent.py   # MiniSWEAgent implementation
│   └── dummy_agent.py    # Dummy agent for testing
│
├── arenas/               # Game arena implementations
│   ├── __init__.py       # Arena registry and get_game()
│   ├── arena.py          # Abstract CodeArena base class
│   ├── battlesnake/      # BattleSnake arena
│   ├── battlecode/       # BattleCode arena
│   ├── corewar/          # CoreWar arena
│   ├── halite/           # Halite arena
│   ├── robocode/         # RoboCode arena
│   ├── robotrumble/      # RobotRumble arena
│   ├── huskybench/       # HuskyBench arena
│   └── dummy/            # Dummy arena for testing
│
├── tournaments/          # Tournament orchestration
│   ├── __init__.py
│   ├── tournament.py     # Abstract tournament base class
│   ├── pvp.py            # PvP tournament implementation
│   └── single_player.py  # Single-player tournament
│
├── analysis/             # Post-tournament analysis
│   ├── metrics/          # ELO, TrueSkill calculations
│   ├── viz/              # Visualization generation
│   ├── llm_as_judge/     # LLM-based code analysis
│   └── bootstrap/        # Statistical analysis
│
├── viewer/               # Web-based result viewer
│   ├── app.py            # Flask application
│   └── templates/        # Jinja2 templates
│
└── utils/                # Shared utilities
    ├── environment.py    # Docker container management
    ├── git_utils.py      # Git operations
    ├── yaml_utils.py     # Config parsing with !include
    ├── aws.py            # AWS Batch integration
    └── log.py            # Custom logging
```

## Key Modules

### Entry Point: `main.py`

The CLI entry point. Parses arguments, loads config, and starts a tournament:

```python
# main.py (simplified)
def main(config_path, cleanup=False, push=False, ...):
    config = yaml.safe_load(config_path.read_text())
    tournament = PvpTournament(config, output_dir=..., cleanup=cleanup)
    tournament.run()
```

**When to modify:** Adding new CLI flags or changing tournament initialization.

### Tournaments: `codeclash/tournaments/`

Orchestrates the multi-round edit+compete loop.

```python
# tournaments/pvp.py (simplified)
class PvpTournament(AbstractTournament):
    def run(self):
        for round_num in range(self.rounds):
            # Edit phase: agents modify their code
            for agent in self.agents:
                agent.run(round_num)

            # Compete phase: run game simulations
            results = self.arena.run_round(round_num)
            self.record_results(results)
```

**Key classes:**

- `AbstractTournament` - Base class with common logic
- `PvpTournament` - Multi-player competitive tournaments
- `SinglePlayerTournament` - Single agent improvement tracking

**When to modify:** Adding new tournament types or changing the round loop.

### Arenas: `codeclash/arenas/`

Game implementations that run competitions between agent codebases.

```python
# arenas/arena.py (simplified)
class CodeArena(ABC):
    name: str  # e.g., "BattleSnake"

    def run_round(self, agents, round_num: int) -> RoundStats:
        """Execute one round of the game (concrete method)."""
        # Calls execute_round() and get_results() internally
        pass

    @abstractmethod
    def execute_round(self, agents) -> None:
        """Game-specific execution logic."""
        pass

    @abstractmethod
    def validate_code(self, agent) -> tuple[bool, str | None]:
        """Check if agent's code compiles/runs."""
        pass

    @abstractmethod
    def get_results(self, agents, round_num: int, stats: RoundStats):
        """Determine winner based on game output."""
        pass
```

**Arena registry** (`arenas/__init__.py`):

```python
ARENAS = [BattleCodeArena, BattleSnakeArena, CoreWarArena, HaliteArena,
          HuskyBenchArena, RoboCodeArena, RobotRumbleArena, ...]

def get_game(config: dict, **kwargs) -> CodeArena:
    game = {x.name: x for x in ARENAS}.get(config["game"]["name"])
    return game(config, **kwargs)
```

**When to modify:** Adding new games or changing game mechanics.

### Agents: `codeclash/agents/`

AI agents that modify code during the edit phase.

```python
# agents/player.py (simplified)
class Player(ABC):
    @abstractmethod
    def run(self) -> None:
        """Execute agent's code improvement strategy."""
        pass

    def pre_run_hook(self):
        """Setup before round execution."""
        pass

    def post_run_hook(self):
        """Cleanup and metadata after round."""
        pass
```

**Agent registry** (`agents/__init__.py`):

```python
def get_agent(config, game_context, environment, push=False) -> Player:
    agents = {"dummy": Dummy, "mini": MiniSWEAgent}
    return agents[config["agent"]](config, environment, game_context, push)
```

**When to modify:** Adding new agent types or changing agent behavior.

### Utilities: `codeclash/utils/`

Shared helper functions:

| Module | Purpose |
|--------|---------|
| `environment.py` | Docker container lifecycle management |
| `git_utils.py` | Git clone, commit, push operations |
| `yaml_utils.py` | Config parsing with `!include` directive |
| `aws.py` | AWS Batch and ECR integration |
| `log.py` | Custom logging with emoji prefixes |

## Extension Points

### Adding a New Arena

1. **Create arena directory:**
   ```
   codeclash/arenas/myarena/
   ├── __init__.py
   ├── myarena.py
   └── Dockerfile  # (if needed)
   ```

2. **Implement the arena class:**
   ```python
   # codeclash/arenas/myarena/myarena.py
   from codeclash.arenas.arena import CodeArena

   class MyArena(CodeArena):
       name = "MyArena"

       def execute_round(self, agents) -> None:
           # Game-specific execution logic
           pass

       def validate_code(self, agent) -> tuple[bool, str | None]:
           # Check if code compiles/runs
           pass

       def get_results(self, agents, round_num, stats):
           # Determine winner based on game output
           pass
   ```

3. **Register the arena:**
   ```python
   # codeclash/arenas/__init__.py
   from codeclash.arenas.myarena.myarena import MyArena

   ARENAS = [..., MyArena]
   ```

4. **Add documentation:**
   - Create `docs/reference/arenas/myarena.md`
   - Add to `mkdocs.yml` navigation

5. **Create example configs:**
   - `configs/test/myarena.yaml` (dummy agents)
   - `configs/examples/MyArena__model1__model2__r5__s100.yaml`

### Adding a New Agent Type

1. **Create agent file:**
   ```python
   # codeclash/agents/myagent.py
   from codeclash.agents.player import Player

   class MyAgent(Player):
       def run(self) -> None:
           # Your code improvement logic
           pass
   ```

2. **Register the agent:**
   ```python
   # codeclash/agents/__init__.py
   from codeclash.agents.myagent import MyAgent

   def get_agent(...):
       agents = {"dummy": Dummy, "mini": MiniSWEAgent, "my": MyAgent}
       ...
   ```

3. **Add documentation:**
   - Create `docs/reference/player/myagent.md`

### Adding Analysis Tools

Analysis modules live in `codeclash/analysis/`. Common patterns:

```python
# codeclash/analysis/mymetric/compute.py
def compute_metric(tournament_dir: Path) -> dict:
    """Compute custom metric from tournament results."""
    results = json.loads((tournament_dir / "tournament_metadata.json").read_text())
    # Your analysis logic
    return {"metric": value}
```

## First Steps for Contributors

### 1. Run the tests

```bash
uv run pytest
```

### 2. Try a test tournament

```bash
uv run python main.py configs/test/battlesnake.yaml
```

### 3. Explore an existing arena

Read through `codeclash/arenas/battlesnake/battlesnake.py` to understand:

- How Docker images are built
- How games are executed
- How results are parsed

### 4. Trace a tournament run

Add some print statements or use a debugger:

```bash
uv run python -m pdb main.py configs/test/battlesnake.yaml
```

### 5. Check the viewer

```bash
uv run python scripts/run_viewer.py -d logs/*/PvpTournament.*
```

## Code Style

- **Formatting:** Ruff (Black-compatible)
- **Linting:** Ruff
- **Type hints:** Encouraged but not required everywhere
- **Docstrings:** Google style

```bash
# Format and lint
uv run ruff format .
uv run ruff check . --fix
```

## Common Tasks

| Task | Location |
|------|----------|
| Add CLI flag | `main.py:main_cli()` |
| Change tournament flow | `tournaments/pvp.py` |
| Add new game | `arenas/<game>/<game>.py` |
| Add new agent | `agents/<agent>.py` |
| Add new metric | `analysis/metrics/` |
| Change Docker behavior | `utils/environment.py` |
| Modify config parsing | `utils/yaml_utils.py` |

## Getting Help

- **Issues:** [GitHub Issues](https://github.com/CodeClash-ai/CodeClash/issues)
- **Discussions:** Open an issue to discuss ideas
- **Contact:** John Yang (johnby@stanford.edu), Kilian Lieret (kl5675@princeton.edu)

--8<-- "docs/_footer.md"
