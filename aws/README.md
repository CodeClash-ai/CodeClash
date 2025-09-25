# AWS

## Usage

```bash
# Hello world example
aws/run_job.py --show-logs -- echo "hello world"

# Run main.py with a config file
# Remember to use the docker_and_sync.sh wrapper script!
# ❌ aws/run_job.py --show-logs -- python main.py configs/test/battlesnake_pvp_test.yaml
aws/run_job.py --show-logs -- aws/docker_and_sync.sh python main.py configs/test/battlesnake_pvp_test.yaml
```

> [!WARNING]
> Everything needs to be committed & pushed to the repo! You can use a different branch than main for this.

## Setup

* `setup/`: Everything needed to set up AWS to run codeclash jobs. Advanced user stuff.
