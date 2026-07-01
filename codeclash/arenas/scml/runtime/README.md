# SCML OneShot CodeClash Workspace

Edit `scml_agent.py`.

Your file must define `decide(observation)`. The trusted runtime calls it with plain dictionaries
for SCML proposal and response events. Return `{}` or `None` to use the trusted greedy fallback.

```python
def decide(observation):
    return {}
```

For `event == "propose"`, return `{"offer": [quantity, time, unit_price]}` to make a proposal.
For `event == "respond"`, return `{"response": "accept"}`, `{"response": "reject"}`, or
`{"response": "end"}`. Invalid decisions fall back to the trusted greedy policy.

The arena runs multiple two-process SCML2024 OneShot worlds and scores policies by average profit.
