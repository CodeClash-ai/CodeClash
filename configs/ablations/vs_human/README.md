# vs. Human

These set of configurations correspond to Section 4.1 of the original paper, specifically the subsection *On RobotRumble, models trail substantially behind expert human programmers*.

Each configuration pits a model against an open source codebase written by a human expert for a particular arena. Across a tournament spanning 15 rounds, the model is allowed the evolve the codebase as it sees fit to beat the human expert's solution. The human's solution is *not* changing for the duration of the tournament.

To make models compete against static human solutions, do the following two steps.

1. Make sure the human solution is working and pushed as a branch to the corresponding arena. E.g. [gigachad](https://github.com/CodeClash-ai/RobotRumble/tree/human/entropicdrifter/gigachad) for RobotRumble.
2. Then, in your configuration, simply specify one of the players as a `dummy` agent, with `branch_init` set to the branch name, such as:

```yaml
players:
- agent: dummy
  branch_init: human/entropicdrifter/gigachad
  name: gigachad
```
