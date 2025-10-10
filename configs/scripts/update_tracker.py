import json
from pathlib import Path

tracker = json.load(open("configs/scripts/main_tracker.json"))
arena_logs = [p.parent for p in Path("logs").rglob("metadata.json")]

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
    if arena == "RoboCode":
        with open(arena_log / "metadata.json") as f:
            metadata = json.load(f)
            pvp = ".".join(
                sorted([p["config"]["model"]["model_name"].split("/")[-1] for p in metadata["config"]["players"]])
            )

    if arena in tracker and setting in tracker[arena] and pvp in tracker[arena][setting]:
        tracker[arena][setting][pvp][0] += 1
        rounds_played = len(json.load(open(arena_log / "metadata.json"))["round_stats"])
        tracker[arena][setting][pvp][1] += rounds_played

for arena in sorted(tracker.keys()):
    print(arena)
    for setting in sorted(tracker[arena].keys()):
        print(f"  * {setting}")
        for pvp in sorted(tracker[arena][setting].keys()):
            v = tracker[arena][setting][pvp]
            v_str = f"{v[0]} ({v[1]} rounds)"
            if v[1] > 0:
                print(f"    - {arena}.{setting}.{pvp}: {v_str}")
            tracker[arena][setting][pvp] = v_str

print("Updated tracking file to 'configs/scripts/main_tracker.json'.")
with open("configs/scripts/main_tracker.json", "w") as f:
    json.dump(tracker, f, indent=2)
