# Transparent Codebases

These set of configurations correspond to Section 4.1 of the original paper, specifically *Models have limited capacity for opponent analysis even with transparent codebases.*.

Under normal CodeClash circumstances, models' codebases are not made available to one another. One of CodeClash's challenges is to see whether models are capable of discerning opponent behavior via logs.

In this ablation, we explore lifting this restriction. Each round, in addition to the competition logs, opponents' codebases are also made available to each player. All that's required to enable this feature is to set:

```yaml
tournament:
    ...
    transparent: true
``
