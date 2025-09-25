# Configuration Scripts

To generate all configuration files for tournaments to be run for the main results, run
```bash
python configs/scripts/generate_confs.py
```

This generates a couple things:
* `configs/main/` containing all `*.yaml` configuration files for all tournaments to be run.
* `configs/scripts/main_tracker.json` containing a tracking dictionary to keep track of which tournaments have been run how many times

To update the tournaments run against the `logs/` directory, run
```bash
python configs/scripts/update_tracker.py
```
