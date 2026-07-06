#!/usr/bin/env bash
# Stage 2: play every stage-1-passing port against the reference bot through the REAL Gomoku
# engine (engine.py) inside the arena Docker image, to confirm each loads and plays full games
# without erroring/hanging. Gomoku is 2-player, so each candidate plays the reference bot.
# Writes a per-port verdict table (ports/_stage2.json). Run after validate_ports.py.
#   bash scripts/ladder/run_smoke_all.sh
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PORTS="$REPO_ROOT/scripts/ladder/ports"
EX="$REPO_ROOT/scripts/ladder/examples"
OUT="$REPO_ROOT/scripts/ladder/out"
IMAGE="gomoku-smoke:latest"
PY="$(command -v python3 || command -v python)"

cd "$REPO_ROOT"
docker build -q -f codeclash/arenas/gomoku/Gomoku.Dockerfile -t "$IMAGE" . >/dev/null
mkdir -p "$OUT"

"$PY" - "$PORTS" "$EX" "$OUT" "$IMAGE" <<'PY'
import json, re, subprocess, sys
from pathlib import Path

ports, ex, outdir, image = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
stage1 = json.loads((ports / "_stage1.json").read_text())
files = [n for n, r in sorted(stage1.items()) if r["pass"]]
ROUNDS = 6
verdict = {}
for i, name in enumerate(files):
    stem = name[:-3]
    # candidate is player1, reference bot is player2
    cmd = ["docker", "run", "--rm",
           "-v", f"{ports}:/ports:ro", "-v", f"{ex}:/ex:ro",
           image, "python", "engine.py", f"/ports/{name}", "/ex/main.py", "-r", str(ROUNDS)]
    print(f"  [{i+1}/{len(files)}] {stem} vs reference ...", flush=True)
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        out = p.stdout
    except subprocess.TimeoutExpired:
        verdict[stem] = {"ran": False, "reason": "timeout (>180s) — too slow"}
        continue
    (outdir / f"{stem}.log").write_text(out)
    if "FINAL_RESULTS" not in out:
        verdict[stem] = {"ran": False, "reason": (p.stderr or out)[-200:]}
        continue
    errors = out.count("(error:")
    m1 = re.search(r"Bot_1_main:\s(\d+)\srounds\swon", out)   # candidate = player1
    won = int(m1.group(1)) if m1 else 0
    verdict[stem] = {"ran": True, "errors": errors, "rounds_won_vs_ref": won, "of": ROUNDS}

(ports / "_stage2.json").write_text(json.dumps(verdict, indent=2, sort_keys=True))
print("\n=== STAGE 2 VERDICTS (candidate vs reference bot) ===")
ok = bad = 0
for name in sorted(verdict):
    v = verdict[name]
    good = v.get("ran") and v.get("errors", 1) == 0
    ok += good; bad += not good
    tag = "OK  " if good else "BAD "
    extra = f"won {v.get('rounds_won_vs_ref')}/{v.get('of')} vs ref" if v.get("ran") else v.get("reason","")
    print(f"  {tag} {name}: {extra}" + (f"  errors={v['errors']}" if v.get('errors') else ""))
print(f"\nStage 2: {ok} healthy / {bad} problematic of {len(verdict)}")
PY
