# OpenAI Benchmark Feedback

Date: March 10, 2026

## What We Ran

We evaluated OpenAI coding models in a long-horizon iterative coding benchmark across six arenas:

- BattleSnake
- CoreWar
- Halite
- HuskyBench
- RoboCode
- RobotRumble

Each matchup ran for 15 edit-and-play rounds. This is not a one-shot code generation benchmark; the models repeatedly edited their agents over time using feedback from prior rounds.

## Sweep 1: Prior Pooled Sweep

Run root:
`/Users/muhtasham/Documents/CodeClash/logs/new_openai_sweep_20260307_184312`

Shareable plot:
`/Users/muhtasham/Documents/CodeClash/logs/new_openai_sweep_20260307_184312/analysis/elo/openai_feedback_per_arena.png`

Overall pooled Elo:

- GPT-5.4: 1298 +/- 98
- GPT-5: 1210 +/- 65
- GPT-5.3-Codex: 1092 +/- 108

Interpretation:

- GPT-5.4 was the strongest overall model in the pooled sweep.
- GPT-5 was generally in the middle.
- GPT-5.3-Codex trailed overall.

Important nuance:

- GPT-5 still looked stronger in some arenas, especially Halite and HuskyBench.
- GPT-5.4 appears to win overall because it was stronger more consistently across the full suite, especially in BattleSnake and in the aggregate ranking.

## Sweep 2: Direct GPT-5.4 vs GPT-5.3-Codex by Reasoning Mode

Run root:
`/Users/muhtasham/Documents/CodeClash/logs/gpt54_vs_gpt53codex_reasoning_20260308_164105`

Shareable plots:

- Direct win rate by reasoning mode:
  `/Users/muhtasham/Documents/CodeClash/logs/gpt54_vs_gpt53codex_reasoning_20260308_164105/analysis/shareable/reasoning_mode_win_rate.png`
- GPT-5.4 win rate by arena and reasoning mode:
  `/Users/muhtasham/Documents/CodeClash/logs/gpt54_vs_gpt53codex_reasoning_20260308_164105/analysis/shareable/reasoning_mode_arena_heatmap.png`
- 8-variant Elo view:
  `/Users/muhtasham/Documents/CodeClash/logs/gpt54_vs_gpt53codex_reasoning_20260308_164105/analysis/elo/all_games_elo.png`

Matched-tier direct head-to-head results, excluding ties:

- Default: GPT-5.4 won 57, GPT-5.3-Codex won 37, ties 2
- Low: GPT-5.4 won 48, GPT-5.3-Codex won 45, ties 3
- Medium: GPT-5.4 won 81, GPT-5.3-Codex won 14, ties 1
- High: GPT-5.4 won 62, GPT-5.3-Codex won 22, ties 12

Interpretation:

- GPT-5.4 beat GPT-5.3-Codex at every matched reasoning tier in this direct sweep.
- Medium was the strongest GPT-5.4 setting in this benchmark.
- High was also strong, but not clearly better than Medium.
- Low was close to parity.

Arena-level pattern:

- GPT-5.4 was very strong in RoboCode across all tiers.
- GPT-5.4 Medium was especially strong in CoreWar, Halite, HuskyBench, RoboCode, and RobotRumble.
- GPT-5.3-Codex remained competitive or better in some BattleSnake settings.

## Caveat on the 8-Variant Elo

The 8-way Elo chart for the reasoning sweep should be treated as directional, not definitive.

Reason:

- the sweep only included same-tier direct pairings
- the comparison graph is split into four disconnected components
- there are no bridge matches between tiers

So the most reliable conclusion from Sweep 2 is the direct same-tier head-to-head result, not the exact cross-tier Elo spacing among all eight variants.

## Suggested Product Feedback

- GPT-5.4 looks stronger than GPT-5.3-Codex on long-horizon iterative code improvement, especially at Medium reasoning.
- More reasoning did not monotonically improve results; Medium outperformed High in this setup.
- Performance remains arena-dependent. GPT-5 still looked strong in some environments in the pooled sweep, so model choice may depend on task structure rather than only aggregate Elo.
- For future benchmarking, a connected round-robin across reasoning settings would produce a more trustworthy shared Elo ladder.
