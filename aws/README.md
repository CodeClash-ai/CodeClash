# AWS

## Usage

> [!WARNING]
> Everything needs to be committed & pushed to the repo! You can use a different branch than main for this.

> [!NOTE]
> Most scripts should now have the region default hardcoded, but if things mysterously don't exist, your region or account might not be set up correctly.

### Submit batch jobs

Create a text file that contains the names of the config files you want to run, one per line.
For example:

```
HuskyBench__claude-sonnet-4-20250514__claude-sonnet-4-5-20250929__r15__s100.yaml
HuskyBench__claude-sonnet-4-20250514__gemini-2.5-pro__r15__s100.yaml
HuskyBench__claude-sonnet-4-20250514__gpt-5-mini__r15__s100.yaml
```

If you want to run things multiple times, just duplicate the lines.

Then run:

```bash
python batch_submit.py configs/to_run.txt
```

If the configs are not in `configs/main`, you can use the `--config-dir` flag to specify a different directory.

### Submit single jobs or anything else

```bash
# Hello world example
aws/run_job.py --show-logs -- echo "hello world"

# Run main.py with a config file
# Remember to use the docker_and_sync.sh wrapper script!
# ❌ aws/run_job.py --show-logs -- python main.py configs/test/battlesnake_pvp_test.yaml
aws/run_job.py --show-logs -- aws/docker_and_sync.sh python main.py configs/test/battlesnake_pvp_test.yaml
```

## Once jobs are running

Head to https://emagedoc.xyz/batch for the monitor.

Note: For all features to work (link to s3 folder, viewer, etc.), you need to have the logs synced.
Without the logs you will only see job status, runtime etc.

### Taking actions

* Select runs that might have problems and click "Bulk actions"
* This is a generator for commands to take actions on the runs (e.g., terminate, remove S3 folder etc.)

### Dealing with failures

The best way to find failures is to either select those with the `Failed` status,
or with `Succeeded` but `Incomplete rounds`.

When you believe that something has failed because it doesn't have all rounds completed,
make sure to check the s3 folder for the presence of logs (else there might be a missing sync
so the viewer doesn't have the most recent completed rounds).

Proceed as follows:

1. Select them all
2. Bulk action -> generate resubmit commands
3. Execute those
4. Bulk action -> generate `s3 rm` commands
5. Execute the rm commands

Now you've resubmitted them and removed the partial run S3 folders.

You can also still investigate the failure reason with the AWS console.
In the log viewing window, select sorting -> Desc., then click `Filter logs`.

## Setup

* `setup/`: Everything needed to set up AWS to run codeclash jobs. Advanced user stuff.
