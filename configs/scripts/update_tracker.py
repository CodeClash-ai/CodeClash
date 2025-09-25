import json
from collections import Counter
from pathlib import Path

tracker = json.load(open("configs/scripts/main_tracker.json"))
arena_logs = [p.parent for p in Path("logs").rglob("game.log")]

tournaments = []
for arena_log in arena_logs:
    arena = arena_log.stem.split(".", 2)[1]
    k = arena_log.stem.split(".", 2)[-1]
    if arena in tracker and k in tracker[arena]:
        tracker[arena][k] += 1
        tournaments.append((arena, k))

with open("configs/scripts/main_tracker.json", "w") as f:
    json.dump(tracker, f, indent=2)

print("Updated tracking file to 'configs/scripts/main_tracker.json'.")
print(f"Found {len(tournaments)} tournaments completed:")
for t, num in dict(Counter([f"{t[0]}:{t[1]}" for t in tournaments])).items():
    print(f"- {t}: {num}")
