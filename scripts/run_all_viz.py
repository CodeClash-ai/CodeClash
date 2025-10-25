#!/usr/bin/env python3
"""Run all visualization scripts in codeclash/analysis/viz/"""

from codeclash import REPO_DIR

viz_dir = REPO_DIR / "codeclash" / "analysis" / "viz"

for script in sorted(viz_dir.glob("*.py")):
    if script.name.startswith("_") or script.name == "utils.py":
        continue

    print(f"\n{'=' * 70}")
    print(f"Running: {script.name}")
    print("=" * 70)

    exec(open(script).read())
