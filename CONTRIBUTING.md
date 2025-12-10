# Contributing to CodeClash

Thanks for your interest in contributing to CodeClash!

We're actively working on expanding the coverage of CodeClash in terms of models, arenas, and evaluation techniques. We'd love your help!

## Ideas and Discussions

We have a [living document](https://docs.google.com/document/d/17-Jcexy1KDAbxXILH-GlHrFwGTpLG5yml-0OMFfgnZU/edit?usp=sharing) where we track ideas and contributions we're excited about.

Have suggestions? Please open an issue, and let's discuss!

## Development Setup

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) - Fast Python package manager
- Docker - For running games in containers
- Git

### Getting Started

```bash
# Clone the repository
git clone https://github.com/CodeClash-ai/CodeClash.git
cd CodeClash

# Install uv (if you haven't already)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies with dev extras
uv sync --extra dev

# Install pre-commit hooks
uv run pre-commit install

# Set up environment variables
cp .env.example .env
# Edit .env with your GITHUB_TOKEN and any LLM API keys
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=codeclash

# Run tests in parallel
uv run pytest -n auto

# Run a specific test file
uv run pytest tests/test_integration.py
```

### Code Quality

We use [ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
# Check for linting issues
uv run ruff check .

# Auto-fix linting issues
uv run ruff check . --fix

# Format code
uv run ruff format .

# Check formatting without changing files
uv run ruff format . --check
```

Pre-commit hooks will run these checks automatically before each commit.

### Documentation

We use [MkDocs Material](https://squidfunk.github.io/mkdocs-material/) for documentation:

```bash
# Install docs dependencies
uv sync --extra docs

# Preview docs locally (with hot reload)
uv run mkdocs serve

# Build static docs
uv run mkdocs build
```

Documentation lives in the `docs/` directory.

## Project Structure

```
CodeClash/
├── codeclash/
│   ├── agents/          # AI agent implementations (MiniSWEAgent, etc.)
│   ├── arenas/          # Game arena implementations
│   ├── analysis/        # Post-tournament analysis tools
│   ├── tournaments/     # Tournament orchestration
│   ├── viewer/          # Web-based results viewer
│   └── utils/           # Shared utilities
├── configs/             # Tournament configuration files
├── docs/                # Documentation (MkDocs)
├── tests/               # Test suite
└── main.py              # Main entry point
```

## Types of Contributions

### Adding a New Arena

1. Create a new file in `codeclash/arenas/`
2. Extend the `CodeArena` abstract class
3. Implement required methods: `execute_round()`, `validate_code()`, `get_results()`
4. Add documentation in `docs/reference/arenas/`
5. Add example configs in `configs/`

### Adding a New Agent Type

1. Create a new file in `codeclash/agents/`
2. Extend the `Player` abstract class
3. Implement the `run()` method for code improvement logic
4. Add documentation in `docs/reference/player/`

### Improving Analysis Tools

Analysis tools live in `codeclash/analysis/`. We're particularly interested in:

- New metrics for evaluating agent performance
- Better visualization of tournament results
- Statistical analysis improvements

### Bug Fixes and Improvements

- Bug fixes are always welcome!
- Performance improvements
- Documentation improvements
- Test coverage improvements

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and linting (`uv run pytest && uv run ruff check .`)
5. Commit your changes with a descriptive message
6. Push to your fork
7. Open a Pull Request

### PR Guidelines

- Keep PRs focused on a single change
- Add tests for new functionality
- Update documentation as needed
- Follow existing code style (enforced by ruff)

## Common Development Tasks

| Task | Command |
|------|---------|
| Install dependencies | `uv sync --extra dev` |
| Run tests | `uv run pytest` |
| Lint code | `uv run ruff check .` |
| Format code | `uv run ruff format .` |
| Preview docs | `uv run mkdocs serve` |
| Build wheel | `uv build --wheel` |
| Build wheel + sdist | `uv build` |
| Run a tournament | `uv run python main.py <config>` |
| View results | `uv run python scripts/run_viewer.py` |

### Building Distributions

To build a distributable wheel package:

```bash
# Build wheel only
uv build --wheel

# Build both wheel and source distribution
uv build

# Build with clean output directory
uv build --wheel --clear
```

Built artifacts will be placed in the `dist/` directory by default.

## Contact

- **John Yang**: [johnby@stanford.edu](mailto:johnby@stanford.edu)
- **Kilian Lieret**: [kl5675@princeton.edu](mailto:kl5675@princeton.edu)

Feel free to reach out with questions or ideas!
