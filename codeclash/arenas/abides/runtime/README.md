# ABIDES CodeClash Workspace

Edit `abides_agent.py`.

Your file must define `MyAgent`, an ABIDES trading-agent class. A safe starting point is:

```python
from agent.ValueAgent import ValueAgent as MyAgent
```

The arena runs compact ABIDES market simulations and scores agents by average mark-to-market profit
across identical seeded market worlds.
Scores are computed from exchange execution messages, so editing `self.holdings` directly does not
create scored profit.
Some upstream ABIDES agents keep default behavior behind exact-class checks. If you subclass one of
those agents, override the relevant hooks instead of relying on an empty subclass. Inspect method
signatures before overriding them; common signatures are `wakeup(self, currentTime)`,
`receiveMessage(self, currentTime, msg)`, `kernelStarting(self, startTime)`, and
`kernelStopping(self)`.
