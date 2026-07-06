#!/usr/bin/env bash
# Stage 2 (the real gate): for EVERY port, replicate exactly what the arena does — copy into
# robots/<slug>/, sed custom->slug, `javac -cp libs/robocode.jar`, then RUN A REAL BATTLE
# (<slug>.MyTank vs sample.Walls, 3 rounds) headless in the arena Docker image. Confirms each bot
# actually COMPILES and PLAYS. Writes ports/_stage2.json + per-bot compile/results logs in out/.
#   bash scripts/ladder/run_smoke_all.sh
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PORTS="$REPO_ROOT/scripts/ladder/ports"
OUT="$REPO_ROOT/scripts/ladder/out"
IMAGE="robocode-smoke:latest"
PY="$(command -v python3 || command -v python)"

cd "$REPO_ROOT"
echo "==> Building RoboCode arena image (clones CodeClash-ai/RoboCode; Maven/Temurin — may take a few min)"
docker build -q -f codeclash/arenas/robocode/RoboCode.Dockerfile -t "$IMAGE" . >/dev/null
mkdir -p "$OUT"

# container-side loop: compile + battle each ports/<slug>/ exactly like the arena
cat > "$OUT/_loop.sh" <<'LOOP'
#!/bin/bash
cd /workspace
for d in /ports/*/; do
  slug=$(basename "$d")
  rm -rf robots/$slug; mkdir -p robots/$slug
  cp "$d"*.java robots/$slug/ 2>/dev/null
  find robots/$slug/ -name '*.java' -exec sed -i "s/custom/$slug/g" {} +
  comp=fail
  if javac -cp "libs/robocode.jar" robots/$slug/*.java >/out/$slug.compile.log 2>&1; then
    [ -f robots/$slug/MyTank.class ] && comp=ok
  fi
  batt=skip
  if [ "$comp" = ok ]; then
    cat > battles/smoke_$slug.battle <<BATTLE
#Battle Properties
robocode.battle.numRounds=3
robocode.battleField.width=800
robocode.battleField.height=600
robocode.battle.selectedRobots=$slug.MyTank*,sample.Walls*
BATTLE
    chmod +x robocode.sh 2>/dev/null || true
    if timeout 90 ./robocode.sh -nodisplay -nosound -battle battles/smoke_$slug.battle -results /out/$slug.results >/out/$slug.battle.log 2>&1; then
      batt=ok
    else
      batt=fail
    fi
  fi
  echo "SMOKE $slug compile=$comp battle=$batt"
done
LOOP

echo "==> Compiling + battling each port in the arena image ..."
docker run --rm -v "$PORTS:/ports:ro" -v "$OUT:/out" "$IMAGE" bash /out/_loop.sh | tee "$OUT/_smoke.out"

"$PY" - "$PORTS" "$OUT" <<'PY'
import json, re, sys
from pathlib import Path
ports, out = Path(sys.argv[1]), Path(sys.argv[2])
status = {}
for line in (out / "_smoke.out").read_text().splitlines():
    m = re.match(r"SMOKE (\S+) compile=(\S+) battle=(\S+)", line)
    if m:
        status[m.group(1)] = {"compile": m.group(2), "battle": m.group(3)}
verdict = {}
for slug, s in sorted(status.items()):
    scored = False
    rf = out / f"{slug}.results"
    if rf.exists():
        scored = "MyTank" in rf.read_text()
    good = s["compile"] == "ok" and s["battle"] == "ok" and scored
    reason = ""
    if s["compile"] != "ok":
        clog = out / f"{slug}.compile.log"
        reason = "compile FAILED: " + (clog.read_text().strip().splitlines()[-1][:120] if clog.exists() else "")
    elif s["battle"] != "ok":
        reason = f"battle {s['battle']}"
    elif not scored:
        reason = "no MyTank score in results"
    verdict[slug] = {"compile": s["compile"], "battle": s["battle"], "scored": scored, "ok": good, "reason": reason}
(ports / "_stage2.json").write_text(json.dumps(verdict, indent=2, sort_keys=True))
print("\n=== STAGE 2 (compile + real battle vs sample.Walls) ===")
ok = bad = 0
for slug in sorted(verdict):
    v = verdict[slug]; ok += v["ok"]; bad += not v["ok"]
    print(f"  {'OK  ' if v['ok'] else 'BAD '} {slug}" + ("" if v["ok"] else f"   <- {v['reason']}"))
print(f"\nStage 2: {ok} healthy / {bad} problematic of {len(verdict)}")
PY
