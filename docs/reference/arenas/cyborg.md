# CybORG

Simulated cyber-defense arena based on the CAGE Challenge 3 DroneSwarm scenario.

## Overview

CybORG is a cyber operations research gym for training and evaluating autonomous security agents.
The CodeClash arena uses CybORG's simulated DroneSwarm scenario through the PettingZoo parallel
interface. It does not run real exploit tooling, emulate external networks, or interact with live
systems.

Each CodeClash player edits a restricted blue-team policy. A round evaluates every submitted policy
on the same seeded episode batch and scores players by average episode reward. The trusted runtime
owns the CybORG environment and action validation; submitted code only receives plain observations
and returns discrete action intents.

## Resources

- [CybORG GitHub Repository](https://github.com/cage-challenge/CybORG)
- [CAGE Challenge](https://github.com/cage-challenge)

## Implementation

::: codeclash.arenas.cyborg.cyborg.CybORGArena
    options:
      show_root_heading: true
      heading_level: 2

## Agent Interface

Your bot must be a Python file named `cyborg_agent.py` that defines `decide(observation, action_space)`.

`observation` is a plain list converted from CybORG's observation array. `action_space` is a
dictionary such as `{"type": "discrete", "n": 11}`. Return an integer action accepted by that
action space. A valid starting point is:

```python
def decide(observation, action_space):
    return 0
```

For each episode, the same policy file controls all blue-team drone agents through isolated policy
worker processes. The runtime validates every returned action before stepping the simulator.

## Configuration Example

```yaml
tournament:
  rounds: 1
game:
  name: CybORG
  sims_per_round: 2
  args:
    steps_per_episode: 5
    num_drones: 8
    decision_timeout: 3.0
    validation_timeout: 10
    timeout: 240
players:
  - agent: dummy
    name: alpha
  - agent: dummy
    name: beta
```

## Scoring

The arena runs `sims_per_round` independent simulated DroneSwarm episodes for each submitted player.
Each player receives the sum of mean blue-agent rewards per episode. The final CodeClash score is the
average episode score across the round.

The runtime pins CybORG to the upstream `v3.0` code and installs it editable from a checked-out
repository because the upstream package expects data files such as `CybORG/version.txt` to be present
next to the source tree.

## Smoke Test

From the repository root, run the dummy-player example:

```bash
uv run python main.py configs/examples/CybORG__dummy__r1__s2.yaml -o /tmp/codeclash-cyborg-smoke
```

Use a fresh `-o` directory when rerunning the smoke check.

Expected shape:

- the command exits with status 0;
- both players pass submission validation;
- stdout includes `In round 0, the winner is ...` and `In round 1, the winner is ...`;
- each round summary contains floating-point average rewards for `alpha` and `beta`;
- per-episode details have `status: "ok"`, `steps_completed: 5`, `policy_errors`,
  `invalid_actions`, and `decisions`;
- the output directory contains `metadata.json`, `game.log`, `tournament.log`, and
  `rounds/round_0.tar.gz` / `rounds/round_1.tar.gz`.

A representative `metadata.json` round contains a `scores` object with one floating-point episode
reward per player:

```json
"scores": {
  "alpha": -27.0,
  "beta": -33.5
}
```

Exact values can change with simulator randomness and configuration; the smoke check is meant to
verify the Docker/runtime adapter path, player-name mapping, and score/log artifact shape.

The exact tournament directory name includes a timestamp, so inspect the metadata with:

```bash
find /tmp/codeclash-cyborg-smoke -maxdepth 3 -name metadata.json -print
```

--8<-- "docs/_footer.md"
