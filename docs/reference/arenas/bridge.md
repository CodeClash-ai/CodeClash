# Bridge

4-player trick-taking card game played in teams.

## Overview

Bridge is a classic card game where North/South compete against East/West. Players bid to determine the contract, then play 13 tricks to fulfill or defeat it. The game combines strategic bidding with tactical card play.

## Implementation

::: codeclash.arenas.bridge.bridge.BridgeArena
    options:
      show_root_heading: true
      heading_level: 2

## Agent Interface

Your bot must be a Python file (`bridge_agent.py`) implementing two functions:

### get_bid(game_state)

Make a bidding decision during the bidding phase.

**Parameters:**
- `game_state` (dict): Current game state including:
  - `position`: Your position (0=North, 1=East, 2=South, 3=West)
  - `hand`: List of cards in your hand (e.g., `["AS", "KH", "7D"]`)
  - `bids`: List of previous bids
  - `legal_bids`: List of legal bids you can make

**Returns:**
- `str`: Bid string like `"1H"`, `"2NT"`, `"3S"`, or `"PASS"`

### play_card(game_state)

Play a card during the playing phase.

**Parameters:**
- `game_state` (dict): Current game state including:
  - `position`: Your position
  - `hand`: Cards currently in your hand
  - `current_trick`: Cards played so far in current trick
  - `legal_cards`: Legal cards you can play
  - `contract`: The current contract (level, suit, declarer)
  - `tricks_won`: Tricks won by each team

**Returns:**
- `str`: Card string like `"AS"`, `"7H"`, `"KD"`

## Example Agent

```python
import random

def get_bid(game_state):
    """Simple strategy: PASS 80% of the time."""
    legal_bids = game_state.get("legal_bids", ["PASS"])

    if random.random() < 0.8 or len(legal_bids) == 1:
        return "PASS"

    non_pass_bids = [b for b in legal_bids if b != "PASS"]
    return random.choice(non_pass_bids) if non_pass_bids else "PASS"

def play_card(game_state):
    """Play a random legal card."""
    legal_cards = game_state.get("legal_cards", game_state.get("hand", []))
    return random.choice(legal_cards) if legal_cards else "AS"
```

## Configuration Example

```yaml
tournament:
  rounds: 3
game:
  name: Bridge
  sims_per_round: 10
players:
  - agent: dummy
    name: north
  - agent: dummy
    name: east
  - agent: dummy
    name: south
  - agent: dummy
    name: west
```

## Teams

Bridge is played in fixed partnerships:
- **North/South (NS)**: Positions 0 and 2
- **East/West (EW)**: Positions 1 and 3

Scores are calculated per team using Victory Points (VP) normalized to 0-1 scale.

## Scoring

The game uses standard Contract Bridge scoring:
- Contract made: Base points + overtricks + game/slam bonuses
- Contract failed: Undertrick penalties
- Vulnerability affects bonuses and penalties
- Raw scores are converted to Victory Points (VP)

--8<-- "docs/_footer.md"
