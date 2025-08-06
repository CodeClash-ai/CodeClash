# CodeClash: Evaluating LMs as Adaptive Coding Agents
John Yang, Kilian Lieret

### Setup
To install the codebase, run the following:
```bash
> conda create python=3.10 -n codeclash -y;
> conda activate codeclash;
> pip install -e .
```

### Usage
To run `n` rounds of 2+ models competing against one another on a game, run the following:
```bash
python main.py configs/battlesnake.yaml
python main.py configs/robocode.yaml
python main.py configs/robotrumble.yaml
```
