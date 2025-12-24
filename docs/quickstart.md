# Quick Start

Get up and running with CodeClash in minutes!

## Prerequisites

Before you begin, make sure you have:

- **Python 3.11+**
- **[uv](https://docs.astral.sh/uv/)** - An extremely fast Python package manager
- **Docker** - For running games in isolated containers
- **Git** - For version control

## Installation

### 1. Install uv

=== "macOS/Linux"

    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

=== "Windows"

    ```powershell
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

=== "Homebrew"

    ```bash
    brew install uv
    ```

### 2. Clone and set up CodeClash

```bash
git clone https://github.com/CodeClash-ai/CodeClash.git
cd CodeClash
uv sync
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and add your credentials:

```bash
# Required
GITHUB_TOKEN=your_github_token_here

# Add API keys for the LLM providers you want to use
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
```

!!! note "GitHub Token"
    You need a GitHub token with repository access to pull game starter codebases. [Create one here](https://github.com/settings/tokens).

## Verify Your Setup

### Docker Smoke Test

Before running tournaments, verify Docker is working:

```bash
# Check Docker is running
docker info

# Pull a test image to ensure network/permissions work
docker pull python:3.11-slim

# Quick container test
docker run --rm python:3.11-slim python -c "print('Docker works!')"
```

If any of these fail, see [Docker troubleshooting](#docker-issues).

### Test Tournament

Run a minimal test tournament with dummy agents (no LLM calls):

```bash
uv run python main.py configs/test/battlesnake.yaml
```

This verifies:

- Dependencies are installed correctly
- Docker can build and run game containers
- The tournament pipeline works end-to-end

You should see output like:

```
[INFO] Starting tournament...
[INFO] Round 1/3
[INFO] Running game simulations...
[INFO] Tournament complete!
```

## Configuration Tiers

CodeClash configs are organized into tiers:

| Directory | Purpose | LLM Cost | Use When |
|-----------|---------|----------|----------|
| `configs/test/` | Smoke tests with dummy agents | Free | Verifying setup works |
| `configs/examples/` | Short tournaments (5 rounds) | Low | Learning, quick experiments |
| `configs/main/` | Full benchmark runs (15 rounds) | High | Reproducing paper results |
| `configs/ablations/` | Specialized experiments | Varies | Research ablations |

### Test Configs (Free)

No LLM API calls - uses dummy agents that make no changes:

```bash
uv run python main.py configs/test/battlesnake.yaml
```

### Example Configs (Quick Experiments)

Short 5-round tournaments for learning and experimentation:

```bash
# Claude Sonnet 4.5 vs o3 in BattleSnake (5 rounds)
uv run python main.py configs/examples/BattleSnake__claude-sonnet-4-5-20250929__o3__r5__s1000.yaml

# Same matchup in other arenas
uv run python main.py configs/examples/CoreWar__claude-sonnet-4-5-20250929__o3__r5__s1000.yaml
uv run python main.py configs/examples/Halite__claude-sonnet-4-5-20250929__o3__r5__s250.yaml
uv run python main.py configs/examples/RoboCode__claude-sonnet-4-5-20250929__o3__r5__s250.yaml
```

### Main Configs (Full Benchmarks)

Full 15-round tournaments used in the paper:

```bash
# Full BattleSnake tournament
uv run python main.py configs/main/BattleSnake__claude-sonnet-4-5-20250929__o3__r15__s1000.yaml
```

!!! warning "Cost Warning"
    Main configs run 15 rounds with real LLM agents. Expect significant API costs depending on your model choices.

## Viewing Results

After a tournament completes, view results with the interactive viewer:

```bash
uv run python scripts/run_viewer.py
```

Or specify a specific log directory:

```bash
uv run python scripts/run_viewer.py -d logs/<username>/PvpTournament.BattleSnake.r5.s1000...
```

The viewer shows:

- Round-by-round game replays
- Code changes made by each agent
- Win/loss statistics
- Performance metrics

## Quick Recipes

### Run your first real tournament

```bash
# 1. Make sure you have API keys in .env
# 2. Run a short example tournament
uv run python main.py configs/examples/BattleSnake__claude-sonnet-4-5-20250929__o3__r5__s1000.yaml

# 3. View results
uv run python scripts/run_viewer.py
```

### Try a different arena

```bash
# CoreWar - Assembly-like programming battle
uv run python main.py configs/examples/CoreWar__claude-sonnet-4-5-20250929__o3__r5__s1000.yaml

# RobotRumble - Multi-robot combat
uv run python main.py configs/examples/RobotRumble__claude-sonnet-4-5-20250929__o3__r5__s250.yaml
```

### Create a custom matchup

Copy an example config and modify:

```bash
cp configs/examples/BattleSnake__claude-sonnet-4-5-20250929__o3__r5__s1000.yaml configs/my_tournament.yaml
# Edit configs/my_tournament.yaml to change models, rounds, etc.
uv run python main.py configs/my_tournament.yaml
```

## Troubleshooting

### Docker Issues

**"Cannot connect to Docker daemon"**

```bash
# macOS: Start Docker Desktop
open -a Docker

# Linux: Start the Docker service
sudo systemctl start docker
```

**Permission denied on Linux**

```bash
# Add your user to the docker group
sudo usermod -aG docker $USER
# Log out and back in for changes to take effect
```

**Mac-specific issues**

See [Issue #81](https://github.com/CodeClash-ai/CodeClash/issues/81) for macOS-specific workarounds.

### API Key Issues

**"Authentication failed" or "Invalid API key"**

1. Check your `.env` file has the correct keys
2. Ensure there are no extra spaces or quotes around the keys
3. Verify the key is active in your provider's dashboard

### Import Errors

**"ModuleNotFoundError: No module named 'codeclash'"**

```bash
# Make sure you're using uv run
uv run python main.py configs/test/battlesnake.yaml

# Or activate the virtual environment first
source .venv/bin/activate
python main.py configs/test/battlesnake.yaml
```

## Next Steps

- [Running Tournaments](usage/tournaments.md) - CLI flags, config anatomy, advanced usage
- [Codebase Tour](usage/codebase-tour.md) - Understand the architecture
- [API Reference](reference/index.md) - Detailed documentation

--8<-- "docs/_footer.md"
