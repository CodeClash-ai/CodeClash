#!/usr/bin/env bash
# Stage 2: run every stage-1-passing port through the REAL SCML runtime (in the arena
# Docker image), batched, to confirm each loads, makes decisions, and never crashes/floors.
# Writes a per-agent verdict table (scripts/ladder/ports/_stage2.json). Run after validate_ports.py.
# Populate scripts/ladder/ports/ with the candidate *.py first (see PORTING_GUIDE.md).
#   bash scripts/ladder/run_smoke_all.sh
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PORTS="$REPO_ROOT/scripts/ladder/ports"
EX="$REPO_ROOT/scripts/ladder/examples"
OUT="$REPO_ROOT/scripts/ladder/out"
IMAGE="scml-smoke:latest"
PY="$(command -v python3 || command -v python)"

cd "$REPO_ROOT"
docker build -q -f codeclash/arenas/scml/SCML.Dockerfile -t "$IMAGE" . >/dev/null
mkdir -p "$OUT"

"$PY" - "$PORTS" "$EX" "$OUT" "$IMAGE" <<'PY'
import json, subprocess, sys
from pathlib import Path

ports, ex, outdir, image = (Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4])
stage1 = json.loads((ports / "_stage1.json").read_text())
files = [ports / n for n, r in sorted(stage1.items()) if r["pass"]]

# batch into groups of 5; each group includes the example greedy agent as a common anchor
BATCH = 5
verdict = {}
batches = [files[i:i+BATCH] for i in range(0, len(files), BATCH)]
for bi, batch in enumerate(batches):
    args = ["--agent", "anchor_greedy=/ex/scml_agent.py"]
    for f in batch:
        args += ["--agent", f"{f.stem}=/ports/{f.name}"]
    out = f"/out/batch_{bi}.json"
    cmd = ["docker", "run", "--rm",
           "-v", f"{ports}:/ports:ro", "-v", f"{ex}:/ex:ro", "-v", f"{outdir}:/out",
           image, "python", "run_scml.py", "--sims", "1", "--steps", "6",
           "--lines", "2", "--decision-timeout", "5.0", "--output", out] + args
    print(f"  batch {bi+1}/{len(batches)}: {[f.stem for f in batch]}")
    p = subprocess.run(cmd, capture_output=True, text=True)
    res_path = outdir / f"batch_{bi}.json"
    if p.returncode != 0 or not res_path.exists():
        for f in batch:
            verdict[f.stem] = {"ran": False, "err": (p.stderr or p.stdout)[-200:]}
        continue
    res = json.loads(res_path.read_text())
    agg = {}
    for d in res["details"]:
        d = json.loads(d)
        a = agg.setdefault(d["player"], {"decisions": 0, "errors": 0, "score": 0.0, "status": "ok"})
        a["decisions"] += d.get("decisions", 0)
        a["errors"] += d.get("policy_errors", 0)
        a["score"] += d.get("score", 0.0)
        if d.get("status") == "error":
            a["status"] = "error"
    for f in batch:
        a = agg.get(f.stem, {})
        crashed = a.get("status") == "error" or a.get("score", 0) <= -1e6
        verdict[f.stem] = {"ran": True, "decisions": a.get("decisions", 0),
                           "errors": a.get("errors", 0), "crashed": crashed}

(ports / "_stage2.json").write_text(json.dumps(verdict, indent=2, sort_keys=True))
print("\n=== STAGE 2 VERDICTS ===")
ok = bad = 0
for name in sorted(verdict):
    v = verdict[name]
    good = v.get("ran") and not v.get("crashed") and v.get("decisions", 0) > 0 and v.get("errors", 1) == 0
    ok += good; bad += not good
    tag = "OK  " if good else "BAD "
    print(f"  {tag} {name}: {v}")
print(f"\nStage 2: {ok} healthy / {bad} problematic of {len(verdict)}")
PY
