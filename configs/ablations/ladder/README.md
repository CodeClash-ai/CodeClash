# CC:Ladder

For a more static and hill-climb-able version of CodeClash, we introduce CC:Ladder - for each arena, we curate a collection of human-written solutions, determine their relative rankings, and then see how "high up" the ladder models can climb.

For instance, for RobotRumble, we created a ladder by doing the following steps:
1. From the online [leaderboard](https://robotrumble.org/boards/2), we manually crawled all open source, published bots and pushed them as branches to the [CC:RobotRumble](https://github.com/CodeClash-ai/RobotRumble) repository.
2. We then created the `robotrumble.yaml` file in this folder.
3. Next, from the repository root, we run `uv run python scripts/run_ladder.py configs/ablations/ladder/robotrumble.yaml`, which runs PvP Tournaments against all pairs of branches.
4. From these logs, we then calculate win rate to rank all models.

You can follow these steps to create your own "CC:<arena>" ladder.
The tricky part is typically finding a large collection of human solutions for a particular arena.
We've typically found that googling for online leaderboards or awesome-<arena> repositories (e.g. [BattleSnake](https://github.com/BattlesnakeOfficial/awesome-battlesnake)) is a good strategy.
