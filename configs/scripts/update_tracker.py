import json
from pathlib import Path

tracker = json.load(open("configs/scripts/main_tracker.json"))
arena_logs = [p.parent for p in Path("logs").rglob("game.log")]

# Set all tracker values to 0
for arena in tracker:
    for k in tracker[arena]:
        tracker[arena][k] = [0, 0]

for arena_log in arena_logs:
    arena = arena_log.stem.split(".", 2)[1]
    k = arena_log.stem.split(".", 2)[-1]
    if arena in tracker and k in tracker[arena]:
        tracker[arena][k][0] += 1
        rounds_played = len(json.load(open(arena_log / "metadata.json"))["round_stats"])
        tracker[arena][k][1] += rounds_played

for arena in tracker:
    for k in tracker[arena]:
        v = f"{tracker[arena][k][0]} ({tracker[arena][k][1]} rounds)"
        if tracker[arena][k][1] > 0:
            print(f" - {arena}.{k}: {v}")
        tracker[arena][k] = v

print("Updated tracking file to 'configs/scripts/main_tracker.json'.")
with open("configs/scripts/main_tracker.json", "w") as f:
    json.dump(tracker, f, indent=2)
