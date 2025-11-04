# Quick Start

Get up and running with CodeClash in minutes!

## Installation

### Prerequisites

- Python 3.10 or higher
- Docker (for running games in containers)
- Git
- Conda (recommended)

### Setup

1. **Clone the repository:**

```bash
git clone https://github.com/emagedoc/CodeClash.git
cd CodeClash
```

2. **Create a conda environment:**

```bash
conda create -n codeclash python=3.10 -y
conda activate codeclash
```

3. **Install the package:**

```bash
pip install -e '.[dev]'
pre-commit install
```

4. **Set up environment variables:**

Create a `.env` file in the project root:

```bash
GITHUB_TOKEN=your_github_token_here
```

!!! note
    You need a GitHub token with access permissions for the organization to pull game repositories.

## Running Your First Tournament

### Basic PvP Tournament

Run a player-vs-player tournament with 2+ models competing:

```bash
python main.py configs/pvp/battlecode.yaml
```

### Available Games

Try different games:

```bash
# BattleSnake
python main.py configs/pvp/battlesnake.yaml

# RoboCode
python main.py configs/pvp/robocode.yaml

# RobotRumble
python main.py configs/pvp/robotrumble.yaml

# CoreWar
python main.py configs/pvp/corewar.yaml
```

### Viewing Results

After running a tournament, view the results using the interactive viewer:

```bash
python run_viewer.py
```

The viewer will start a local web server. Open your browser to view:

- Game trajectories
- Agent performance metrics
- Round-by-round analysis
- Code changes over time

Use the `-d` flag to specify a custom log directory:

```bash
python run_viewer.py -d path/to/logs
```

## Configuration

Tournament configurations are stored in YAML files under `configs/`. Here's a basic structure:

```yaml
game:
  name: BattleCode
  rounds: 10
  sims_per_round: 3

players:
  - name: Agent1
    model: gpt-4
  - name: Agent2
    model: claude-3-opus
```

See [Running Tournaments](usage/tournaments.md) for detailed configuration options.

## FAQ

### How do I add a new LLM provider?

Configure your model in the agent configuration section of your YAML file. CodeClash supports any provider compatible with LiteLLM.

### Where are logs stored?

By default, logs are stored in the `logs/` directory at the project root. Each tournament creates a subdirectory with a unique ID.

### Can I create custom games?

Yes! Extend the `CodeGame` abstract class. See the [API Reference](reference/arenas/game.md) for details.

### How do I debug agent behavior?

Use the trajectory viewer to step through each round and see:

- Code changes made by the agent
- Game logs and outputs
- Performance metrics
- Error messages

## Next Steps

- [Learn about tournaments](usage/tournaments.md)
- [Explore the API](reference/index.md)
- [Build custom agents](reference/player/player.md)

--8<-- "docs/_footer.md"
