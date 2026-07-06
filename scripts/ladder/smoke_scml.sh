#!/usr/bin/env bash
# Pilot smoke test: run the ported bot vs a dummy through the REAL SCML runtime
# (run_scml.py + scml==0.8.2) inside the arena's own Docker image. No GitHub repo
# needed — this exercises the decide() contract, validation, and real game scoring.
#
#   bash scripts/ladder/smoke_scml.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EX_DIR="$REPO_ROOT/scripts/ladder/examples"
OUT_DIR="$REPO_ROOT/scripts/ladder/out"
IMAGE="scml-smoke:latest"

cd "$REPO_ROOT"
mkdir -p "$OUT_DIR"

echo "==> Building SCML arena image (installs scml==0.8.2 + runtime)"
docker build -q -f codeclash/arenas/scml/SCML.Dockerfile -t "$IMAGE" . >/dev/null

echo "==> Running: greedy (example) vs dummy — 2 sims, 8 steps, 2 lines"
docker run --rm \
  -v "$EX_DIR:/ex:ro" \
  -v "$OUT_DIR:/out" \
  "$IMAGE" \
  python run_scml.py \
    --agent greedy=/ex/scml_agent.py \
    --agent dummy=/ex/dummy_agent.py \
    --sims 2 --steps 8 --lines 2 \
    --decision-timeout 5.0 \
    --output /out/scml_results.json

echo "==> Result (scripts/ladder/out/scml_results.json):"
PY_BIN="$(command -v python3 || command -v python)"
"$PY_BIN" - "$OUT_DIR/scml_results.json" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))
print("  average_scores:", r["average_scores"])
print("  sims          :", r["sims"])
errs = decisions = 0
for d in r["details"]:
    d = json.loads(d)
    decisions += d.get("decisions", 0)
    errs += d.get("policy_errors", 0)
    if d.get("status") == "error":
        print("  !! ERROR", d["player"], d.get("error"))
print(f"  total decide() calls: {decisions}   policy_errors: {errs}")
ok = decisions > 0 and errs == 0 and all(s > -1e6 for s in r["average_scores"].values())
print("  SMOKE:", "PASS ✅" if ok else "FAIL ❌")
sys.exit(0 if ok else 1)
PY
