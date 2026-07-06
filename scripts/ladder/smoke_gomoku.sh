#!/usr/bin/env bash
# Quick smoke: play the reference bot vs the arena's default main.py through the REAL Gomoku
# engine inside the arena Docker image. No GitHub token needed — confirms the image builds and
# the engine + get_move contract run end-to-end.
#   bash scripts/ladder/smoke_gomoku.sh
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EX="$REPO_ROOT/scripts/ladder/examples"
IMAGE="gomoku-smoke:latest"

cd "$REPO_ROOT"
echo "==> Building Gomoku arena image (clones CodeClash-ai/Gomoku engine)"
docker build -q -f codeclash/arenas/gomoku/Gomoku.Dockerfile -t "$IMAGE" . >/dev/null

echo "==> Running: reference bot vs the repo's default main.py — 6 games"
# reference is player1; the image ships the arena's default bot at /workspace/main.py (player2)
out="$(docker run --rm -v "$EX:/ex:ro" "$IMAGE" python engine.py /ex/main.py main.py -r 6)"
echo "$out" | sed -n '/FINAL_RESULTS/,$p'
if echo "$out" | grep -q "FINAL_RESULTS" && ! echo "$out" | grep -q "(error:"; then
  echo "SMOKE: PASS ✅"
else
  echo "SMOKE: FAIL ❌"; exit 1
fi
