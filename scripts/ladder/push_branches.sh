#!/usr/bin/env bash
# Push every stage-2-healthy port to CodeClash-ai/Gomoku as a human/gomoku/<slug> branch,
# with the port placed as the arena submission file main.py.
# Port "colingogogo.py" -> branch "human/gomoku/colingogogo". Dedupes identical content.
#   bash scripts/ladder/push_branches.sh
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PORTS="$REPO_ROOT/scripts/ladder/ports"
ARENA_REPO="CodeClash-ai/Gomoku"
SUBMISSION="main.py"
SKIP="zhoukangyang"   # NN/AlphaZero source with no rule-based path; the port is a uniform-prior
                      # UCT substitute (not faithful; duplicates tsrmkumoko) -> defer

TMP=$(mktemp -d)
git clone -q "https://x-access-token:$(gh auth token)@github.com/${ARENA_REPO}.git" "$TMP"
cd "$TMP"
git checkout -q main

SEEN=$(mktemp)
pushed=0; skipped=0
PY="$(command -v python3 || command -v python)"
OKS=$("$PY" -c "import json;d=json.load(open('$PORTS/_stage2.json'));print('\n'.join(k for k,v in sorted(d.items()) if v.get('ran') and v.get('errors',1)==0))")

for stem in $OKS; do
  stem="${stem%.py}"
  case " $SKIP " in *" $stem "*) echo "SKIP  $stem (deferred)"; skipped=$((skipped+1)); continue;; esac
  h=$(shasum "$PORTS/$stem.py" | awk '{print $1}')
  if grep -q "^$h " "$SEEN"; then echo "SKIP  $stem (dup of $(grep "^$h " "$SEEN" | awk '{print $2}'))"; skipped=$((skipped+1)); continue; fi
  echo "$h $stem" >> "$SEEN"
  branch="human/gomoku/$stem"
  git checkout -q main
  git checkout -q -B "$branch"
  cp "$PORTS/$stem.py" "$SUBMISSION"
  git add "$SUBMISSION"
  git -c user.email=player@codeclash.com -c user.name="CodeClash" commit -qm "Import $stem (Gomoku ladder)"
  git push -q -f -u origin "$branch" 2>/dev/null
  echo "PUSH  $branch"
  pushed=$((pushed+1))
done
cd "$REPO_ROOT"; rm -rf "$TMP"
echo "=== pushed $pushed, skipped $skipped ==="
