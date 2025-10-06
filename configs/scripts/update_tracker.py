import json
from pathlib import Path

tracker = json.load(open("configs/scripts/main_tracker.json"))
arena_logs = [p.parent for p in Path("logs/completed").rglob("game.log")]

# Set all tracker values to 0
for arena in tracker:
    for setting in tracker[arena]:
        for k in tracker[arena][setting]:
            tracker[arena][setting][k] = [0, 0]

for arena_log in arena_logs:
    arena = arena_log.stem.split(".", 2)[1]
    k = arena_log.stem.split(".", 2)[-1]
    pvp = k.split(".", 3)[-1]
    setting = k[: -len(pvp) - 1]
    if arena in tracker and setting in tracker[arena] and pvp in tracker[arena][setting]:
        tracker[arena][setting][pvp][0] += 1
        rounds_played = len(json.load(open(arena_log / "metadata.json"))["round_stats"])
        tracker[arena][setting][pvp][1] += rounds_played

for arena in tracker:
    print(arena)
    for setting in tracker[arena]:
        print(f"  * {setting}")
        for pvp, v in tracker[arena][setting].items():
            v_str = f"{v[0]} ({v[1]} rounds)"
            if v[1] > 0:
                print(f"    - {arena}.{setting}.{pvp}: {v_str}")
            tracker[arena][setting][pvp] = v_str

print("Updated tracking file to 'configs/scripts/main_tracker.json'.")
with open("configs/scripts/main_tracker.json", "w") as f:
    json.dump(tracker, f, indent=2)
