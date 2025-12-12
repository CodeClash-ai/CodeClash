# Multi-player competitions

The default CodeClash tournament setting pits players head to head.

In these configurations, we explore how competitive dynamics change when 3+ players are competing. Specifically, we run Core War tournaments lasting 15 rounds with 6 players. Our findings can be found in the original paper in Section 4.1, specifically *Multi-agent competitions (3+ players) reflect similar rankings*.

To enable multi-player competitions, simply add more players under the `players` field in your configuration, such as:

```yaml
players:
- agent: mini
  ...
- agent: mini
  ...
- agent: mini
  ...
```
