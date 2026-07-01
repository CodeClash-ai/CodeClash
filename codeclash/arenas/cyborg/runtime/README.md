# CybORG CodeClash Workspace

Edit `cyborg_agent.py`.

Your file must define `decide(observation, action_space)`. The trusted runtime calls it with:

- `observation`: a plain list converted from the CybORG observation array
- `action_space`: a dictionary such as `{"type": "discrete", "n": 11}`

Return an integer action in `[0, action_space["n"])`:

```python
def decide(observation, action_space):
    return 0
```

The trusted CodeClash runtime owns the CybORG environment and validates returned actions before
stepping the simulation. Submitted code only receives observations and returns action intents.

The arena runs simulated CAGE Challenge 3 DroneSwarm episodes and scores policies by average reward.
