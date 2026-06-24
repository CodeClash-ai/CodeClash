# Static hosting of trajectories

How this works:

1. Run `freeze_viewer.py` to generate the static site in the `build` directory.
2. Push to the github repo. Let's not keep any history to keep things small
3. Deployed to https://viewer.codeclash.ai/

## Commands

> [!CAUTION]
> This will overwrite anything on the public display. Make sure you have all trajectories

```bash
cd REPO_ROOT
aws s3 sync logs/ s3://codeclash/logs/
./build_static_and_push.sh
```
