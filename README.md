# CodeClash: Evaluating LMs as Adaptive Coding Agents
John Yang, Kilian Lieret

### Setup
To install the codebase, run the following:
```bash
conda create -n codeclash python=3.10 -y
conda activate codeclash
pip install -e .
```

### Usage

To build the Docker images for each game:
```bash
docker build -t codeclash/battlesnake -f docker/BattleSnake.Dockerfile .
docker build -t codeclash/robotrumble -f docker/RobotRumble.Dockerfile .
docker build -t codeclash/robocode -f docker/RoboCode.Dockerfile .
```

To run `n` rounds of 2+ models competing against one another on a game, run the following:
```bash
python main.py configs/battlesnake.yaml
python main.py configs/robocode.yaml
python main.py configs/robotrumble.yaml
```
