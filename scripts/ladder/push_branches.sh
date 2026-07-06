#!/usr/bin/env bash
# Push every stage-2-healthy port to CodeClash-ai/RoboCode as a human/robocode/<slug> branch,
# placing the port's .java files in the arena submission dir robots/custom/.
# Port dir scripts/ladder/ports/<slug>/ -> branch human/robocode/<slug> with robots/custom/*.java.
#   bash scripts/ladder/push_branches.sh
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PORTS="$REPO_ROOT/scripts/ladder/ports"
ARENA_REPO="CodeClash-ai/RoboCode"
SKIP=""   # space-separated slugs to defer, if any

TMP=$(mktemp -d)
git clone -q "https://x-access-token:$(gh auth token)@github.com/${ARENA_REPO}.git" "$TMP"
cd "$TMP"
DEFAULT=$(git symbolic-ref --short HEAD)

pushed=0; skipped=0
PY="$(command -v python3 || command -v python)"
OKS=$("$PY" -c "import json;d=json.load(open('$PORTS/_stage2.json'));print('\n'.join(k for k,v in sorted(d.items()) if v.get('ok')))")

for slug in $OKS; do
  case " $SKIP " in *" $slug "*) echo "SKIP  $slug (deferred)"; skipped=$((skipped+1)); continue;; esac
  branch="human/robocode/$slug"
  git checkout -q "$DEFAULT"
  git checkout -q -B "$branch"
  rm -rf robots/custom; mkdir -p robots/custom
  cp "$PORTS/$slug/"*.java robots/custom/
  git add robots/custom
  git -c user.email=player@codeclash.com -c user.name="CodeClash" commit -qm "Import $slug (RoboCode ladder)"
  git push -q -f -u origin "$branch" 2>/dev/null
  echo "PUSH  $branch"
  pushed=$((pushed+1))
done
cd "$REPO_ROOT"; rm -rf "$TMP"
echo "=== pushed $pushed, skipped $skipped ==="
