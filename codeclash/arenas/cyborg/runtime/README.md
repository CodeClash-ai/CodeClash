# CybORG CodeClash Workspace

Edit `cyborg_agent.py`.

Your file must define `MyAgent`, a CybORG `BaseAgent` subclass. A safe starting point is:

```python
from CybORG.Agents import RandomAgent


class MyAgent(RandomAgent):
    pass
```

The arena runs simulated CAGE Challenge 3 DroneSwarm episodes and scores agents by average reward.
