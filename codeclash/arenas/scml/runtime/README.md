# SCML OneShot CodeClash Workspace

Edit `scml_agent.py`.

Your file must define `MyAgent`, an SCML OneShot agent class. A safe starting point is:

```python
from scml.oneshot.agents import GreedySyncAgent


class MyAgent(GreedySyncAgent):
    pass
```

The arena runs multiple SCML2024 OneShot worlds and scores agents by average profit.
