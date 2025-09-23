# CodeClash: Evaluating LMs as Adaptive Coding Agents
John Yang, Kilian Lieret

## Setup

To install the codebase, run the following:
```bash
conda create -n codeclash python=3.10 -y
conda activate codeclash
pip install -e '.[dev]'
pre-commit install
```

Make sure you have `GITHUB_TOKEN` (w/ access permissions for this organization) set in a `.env` file

## Usage

To run `n` rounds of 2+ models competing against one another on a game, run the following:
```bash
python main.py configs/pvp/battlecode.yaml
python main.py configs/pvp/battlesnake.yaml
python main.py configs/pvp/robocode.yaml
python main.py configs/pvp/robotrumble.yaml
python main.py configs/pvp/corewar.yaml
```

For storing `logs/`, we're maintaining an AWS S3 bucket (`s3://codeclash`).
```bash
# To backup your logs:
aws s3 sync logs/ s3://codeclash/logs/
# To retrieve logs
aws s3 sync s3://codeclash/logs/ logs/
```

## Trajectory viewer

Assuming that your logs ar in `logs/`, start the viewer with `python run_viewer.py`. Use `-d` (`--directory`) to specify a custom path to your logs.

To deploy to the static site, run

> [!CAUTION]
> This will overwrite anything on the public display. Make sure you have all trajectories

```bash
cd REPO_ROOT
aws s3 sync logs/ s3://codeclash/logs/
./build_static_and_push.sh
```

## AWS EC2

> [!note]
> This is for an ubuntu aws machine.
> To avoid having to log in to AWS for s3 access, choose the `kilian-ec2-full-s3-access` role (add it in "details")

Instance types: `c6a.32xlarge` (128 CPUs)

```bash
export GITHUB_TOKEN=''

sudo apt update
sudo apt install -y python3-pip python3.12-venv
sudo snap install docker
sudo snap install aws-cli --classic
sudo chmod 666 /var/run/docker.sock

git clone https://klieret:${GITHUB_TOKEN}@github.com/emagedoc/CodeClash.git
cd CodeClash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

aws configure

mkdir logs
aws s3 sync s3://codeclash/logs/ logs/

# if evaluating matrix:
ulimit -n 65536  # increase number of open files
```
