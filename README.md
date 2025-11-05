<p align="center">
  <a href="https://codeclash.ai/">
    <img src="docs/assets/banner.png" style="height: 10em" />
  </a>
</p>

<div align="center">
<a href="https://www.python.org/">
  <img alt="Build" src="https://img.shields.io/badge/Python-3.10+-1f425f.svg?color=purple">
</a>
<a href="https://copyright.princeton.edu/policy">
  <img alt="License" src="https://img.shields.io/badge/License-MIT-blue">
</a>
<a href="https://arxiv.org/abs/2511.00839">
  <img src="https://img.shields.io/badge/arXiv-2511.00839-b31b1b.svg">
</a>
</div>

<hr />

## 👋 Overview

CodeClash is a benchmark for evaluating AI systems on **goal-oriented software engineering**.

Today's AI coding evals are *task*-oriented (e.g., HumanEval, SWE-bench).
Models are given explicit instructions.
We then verify implementations with unit tests.

But building software is fundamentally driven by goals ("improve user retention", "reduce costs", "increase revenue").
Reaching our goals is a self-directed, iterative, and often competitive process.
To capture this dynamism of real software development, we introduce CodeClash!

Check out our [arXiv paper](https://arxiv.org/abs/2511.00839) and [website](https://codeclash.ai/) for the full details!

## 🏎️ Quick Start

To start, follow these steps to set up CodeClash and run a test battle:
```bash
$ git clone git@github.com:CodeClash-ai/CodeClash.git
$ cd CodeClash
$ pip install -e '.[dev]'
$ python main.py configs/test/battlesnake.yaml
```

Once this works, you should be set up to run a real tournament!
To run *Claude Sonnet 4.5* against *o3* in a *BattleSnake* tournament with *5 rounds* and *1000 competition simulations* per round, run:
```bash
$ python main.py configs/examples/BattleSnake__claude-sonnet-4-5-20250929__o3__r5__s1000.yaml
```

## ⚔️ How It Works

<p align="center">
  <img src="docs/assets/flowchart.jpg" style="width: 70%" />
</p>

In CodeClash, 2+ LM agents compete in a **code arena** over the course of a multi-round tournament.

For the duration of the tournament, each agent is iteratively improving their own codebase to win a high-level, competitive objective (e.g., accumulate resources, survive the longest, etc).

Each round consists of two phases:

* Edit phase: LM agents make whatever changes they want to their codebase.
* Competition phase: The modified codebases are pitted against each other in the arena.

Critically, *LMs don't play the game directly*.
Their code serves as their competitive proxy.
The winner is the LM agent who wins the most rounds.

## 🚀 Get Involved

- Check out our [docs](https://codeclash.ai/docs/) for more details on running different arenas, configuring tournaments, etc.
- Explore [2000+ tournaments](https://viewer.codeclash.ai/) via our viewer.
- See our [contribution guide](CONTRIBUTING.md) for what we're excited about!
- Have a big idea? Open an issue, and let's turn it into an [insight](https://codeclash.ai/insights/)!

## 💫 Contributions
We're actively working on several follow ups!
Check out the [Contributing Guide](CONTRIBUTING.md) for more.

Contact Person: [John Yang](https://john-b-yang.github.io/), [Kilian Lieret](https://lieret.net)
(Email: [johnby@stanford.edu](mailto:johnby@stanford.edu), [kl5675@princeton.edu](mailto:kl5675@princeton.edu))

## 🪪 License
MIT. Check `LICENSE` for more information.

## ✍️ Citation

```bibtex
@misc{yang2025codeclashbenchmarkinggoalorientedsoftware,
    title={CodeClash: Benchmarking Goal-Oriented Software Engineering},
    author={John Yang and Kilian Lieret and Joyce Yang and Carlos E. Jimenez and Ofir Press and Ludwig Schmidt and Diyi Yang},
    year={2025},
    eprint={2511.00839},
    archivePrefix={arXiv},
    primaryClass={cs.SE},
    url={https://arxiv.org/abs/2511.00839},
}
```

## 📕 Our Other Projects
<div align="center">
  <a href="https://github.com/SWE-bench/SWE-bench"><img src="docs/assets/swebench_logo_text_below.svg" alt="SWE-bench" height="120px"></a>
  &nbsp;&nbsp;
  <a href="https://github.com/SWE-agent/SWE-agent"><img src="docs/assets/sweagent_logo_text_below.svg" alt="SWE-agent" height="120px"></a>
  &nbsp;&nbsp;
  <a href="https://github.com/SWE-agent/Mini-SWE-Agent"><img src="docs/assets/mini_logo_text_below.svg" alt="Mini-SWE-Agent" height="120px"></a>
  &nbsp;&nbsp;
  <a href="https://github.com/SWE-agent/SWE-ReX"><img src="docs/assets/swerex_logo_text_below.svg" alt="SWE-ReX" height="120px"></a>
  &nbsp;&nbsp;
  <a href="https://github.com/SWE-bench/SWE-smith"><img src="docs/assets/swesmith_logo_text_below.svg" alt="SWE-smith" height="120px"></a>
</div>
