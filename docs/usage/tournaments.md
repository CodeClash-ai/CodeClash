# Running Tournaments

This guide covers everything you need to know about running CodeClash tournaments: CLI options, configuration files, environment variables, and output structure.

## CLI Reference

```bash
uv run python main.py <config_path> [options]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `config_path` | Path to the tournament YAML config file (required) |

### Options

| Flag | Short | Description |
|------|-------|-------------|
| `--cleanup` | `-c` | Clean up game environment after running |
| `--push` | `-p` | Push each agent's final codebase to a new GitHub repository |
| `--output-dir PATH` | `-o PATH` | Custom output directory (default: `logs/<username>/`) |
| `--suffix TEXT` | `-s TEXT` | Suffix to append to the output folder name |
| `--keep-containers` | `-k` | Keep Docker containers after games/agents finish (useful for debugging) |

### Examples

```bash
# Basic run
uv run python main.py configs/examples/BattleSnake__claude-sonnet-4-5-20250929__o3__r5__s1000.yaml

# Keep containers for debugging
uv run python main.py configs/test/battlesnake.yaml -k

# Custom output directory with suffix
uv run python main.py configs/examples/BattleSnake__claude-sonnet-4-5-20250929__o3__r5__s1000.yaml \
    -o ./my_experiments \
    -s experiment1

# Push final codebases to GitHub
uv run python main.py configs/examples/BattleSnake__claude-sonnet-4-5-20250929__o3__r5__s1000.yaml -p
```

## Configuration Anatomy

Tournament configs are YAML files with four main sections:

```yaml
# 1. Tournament settings
tournament:
  rounds: 5                    # Number of edit+compete rounds
  transparent: false           # If true, agents can see opponent's code

# 2. Game/Arena settings
game:
  name: BattleSnake            # Arena name (must match registered arena)
  sims_per_round: 1000         # Number of game simulations per round
  args:                        # Arena-specific arguments
    width: 11
    height: 11
    browser: false

# 3. Player/Agent definitions
players:
- agent: mini                  # Agent type: "mini" or "dummy"
  name: claude-sonnet-4-5      # Display name (used in logs)
  config:
    agent: !include mini/default.yaml
    model:
      model_name: '@anthropic/claude-sonnet-4-5-20250929'
      model_kwargs:
        temperature: 0.2
        max_tokens: 4096

- agent: mini
  name: o3
  config:
    agent: !include mini/default.yaml
    model:
      model_name: '@openai/o3'

# 4. Prompts for agents
prompts:
  game_description: |
    You are a software developer competing in BattleSnake...
```

### The `!include` Directive

CodeClash supports `!include` for reusing config fragments:

```yaml
# In your tournament config
config:
  agent: !include mini/default.yaml    # Includes configs/mini/default.yaml
  model:
    model_name: '@anthropic/claude-sonnet-4-5-20250929'
```

This is especially useful for:

- Sharing agent configurations across tournaments
- Keeping model-specific settings in one place
- Reducing config duplication

Include paths are relative to the `configs/` directory.

### Tournament Section

| Field | Type | Description |
|-------|------|-------------|
| `rounds` | int | Number of tournament rounds (edit + compete cycles) |
| `transparent` | bool | If true, agents can see opponent's code changes |

### Game Section

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Arena name (BattleSnake, CoreWar, Halite, etc.) |
| `sims_per_round` | int | Number of game simulations per round |
| `args` | dict | Arena-specific arguments |

#### Arena-Specific Args

**BattleSnake:**
```yaml
args:
  width: 11          # Board width
  height: 11         # Board height
  browser: false     # Open browser for visualization
```

**CoreWar:**
```yaml
args:
  core_size: 8000    # Memory size
  max_cycles: 80000  # Maximum execution cycles
```

### Players Section

Each player entry defines an AI agent:

| Field | Type | Description |
|-------|------|-------------|
| `agent` | string | Agent type: `mini` (MiniSWEAgent) or `dummy` |
| `name` | string | Display name for logs and results |
| `config` | dict | Agent-specific configuration |
| `config.model` | dict | LLM model settings |
| `config.agent` | dict | Agent behavior settings |

#### Model Configuration

```yaml
model:
  model_name: '@anthropic/claude-sonnet-4-5-20250929'
  model_kwargs:
    temperature: 0.2
    max_tokens: 4096
```

Model names use the `@provider/model` format from [LiteLLM](https://docs.litellm.ai/docs/providers).

### Prompts Section

The `prompts` section defines what agents see:

| Field | Description |
|-------|-------------|
| `game_description` | Main prompt describing the game and task |
| `system` | (Optional) System prompt for the LLM |

Prompts support template variables:

| Variable | Description |
|----------|-------------|
| `{{player_id}}` | Agent's identifier |
| `{{round}}` | Current round number |
| `{{rounds}}` | Total number of rounds |
| `{{working_dir}}` | Path to agent's codebase |

## Environment Variables

### Required

| Variable | Description |
|----------|-------------|
| `GITHUB_TOKEN` | GitHub token for cloning game starter repos |

### LLM Providers

Set API keys for the providers you're using:

| Variable | Provider |
|----------|----------|
| `OPENAI_API_KEY` | OpenAI (GPT-4, o3, etc.) |
| `ANTHROPIC_API_KEY` | Anthropic (Claude) |
| `GOOGLE_API_KEY` | Google (Gemini) |
| `GROQ_API_KEY` | Groq |

### Optional

| Variable | Description |
|----------|-------------|
| `PORTKEY_API_KEY` | Portkey for LLM request management |
| `AWS_ACCESS_KEY_ID` | AWS credentials (for AWS Batch) |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials |
| `AWS_DEFAULT_REGION` | AWS region (default: us-east-1) |

## Output Structure

Tournament logs are saved to `logs/<username>/<tournament_folder>/`:

```
logs/
└── <username>/
    └── PvpTournament.BattleSnake.r5.s1000.p2.claude-sonnet-4-5.o3.241210143022/
        ├── config.yaml              # Copy of tournament config
        ├── tournament_metadata.json # Tournament summary
        ├── round_1/
        │   ├── game_results.json    # Game outcomes for this round
        │   ├── claude-sonnet-4-5/
        │   │   ├── changes.json     # Code changes made by agent
        │   │   ├── trajectory.json  # Agent's action history
        │   │   └── codebase/        # Snapshot of agent's code
        │   └── o3/
        │       ├── changes.json
        │       ├── trajectory.json
        │       └── codebase/
        ├── round_2/
        │   └── ...
        └── round_5/
            └── ...
```

### Folder Naming Convention

```
PvpTournament.<Game>.r<rounds>.s<sims>.p<players>.<player_names>.<timestamp>
```

Example: `PvpTournament.BattleSnake.r5.s1000.p2.claude-sonnet-4-5.o3.241210143022`

### Key Output Files

| File | Contents |
|------|----------|
| `config.yaml` | Complete tournament configuration |
| `tournament_metadata.json` | Overall results, win counts, final scores |
| `round_N/game_results.json` | Per-round game outcomes |
| `round_N/<agent>/changes.json` | Code diffs made by agent |
| `round_N/<agent>/trajectory.json` | LLM conversation/action log |

## Quick Recipes

### Reproduce a paper result

```bash
# BattleSnake: Claude Sonnet 4.5 vs o3 (15 rounds)
uv run python main.py configs/main/BattleSnake__claude-sonnet-4-5-20250929__o3__r15__s1000.yaml
```

### Run all arenas for a matchup

```bash
for arena in BattleSnake CoreWar Halite RoboCode RobotRumble; do
    uv run python main.py "configs/main/${arena}__claude-sonnet-4-5-20250929__o3__r15__s1000.yaml"
done
```

### Debug a failing agent

```bash
# Keep containers for inspection
uv run python main.py configs/test/battlesnake.yaml -k

# Then inspect the container
docker ps -a  # Find container ID
docker logs <container_id>
docker exec -it <container_id> /bin/bash
```

### Quick A/B test with custom suffix

```bash
# Run variant A
uv run python main.py configs/my_config.yaml -s variantA

# Run variant B (modified config)
uv run python main.py configs/my_config_b.yaml -s variantB
```

### Batch run with different models

```bash
#!/bin/bash
models=("claude-sonnet-4-5-20250929" "gpt-5" "gemini-2.5-pro")
for model in "${models[@]}"; do
    config="configs/main/BattleSnake__${model}__o3__r15__s1000.yaml"
    if [ -f "$config" ]; then
        uv run python main.py "$config"
    fi
done
```

## Viewing Results

After tournaments complete:

```bash
# Start the viewer
uv run python scripts/run_viewer.py

# Or specify a log directory
uv run python scripts/run_viewer.py -d logs/<username>/PvpTournament.BattleSnake...
```

See [2000+ tournament results](https://viewer.codeclash.ai/) from the paper.

## Next Steps

- [Codebase Tour](codebase-tour.md) - Understand the architecture
- [API Reference](../reference/index.md) - Detailed class documentation
- [Quick Start](../quickstart.md) - Back to basics

--8<-- "docs/_footer.md"
