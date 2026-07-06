#!/usr/bin/env bash
# Push every stage-2-healthy port to CodeClash-ai/SCML as a human/<author>/<name> branch.
# File stem "scml2021__team_54" -> branch "human/scml2021/team_54".
# Skips ports listed in SKIP. Dedupes exact-duplicate content (keeps first).
#   bash scripts/ladder/push_branches.sh
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PORTS="$REPO_ROOT/scripts/ladder/ports"
SKIP="scml2023__team_139"   # extreme-price bot trips per-negotiation bound mismatch; defer

TMP=$(mktemp -d)
git clone -q "https://x-access-token:$(gh auth token)@github.com/CodeClash-ai/SCML.git" "$TMP"
cd "$TMP"
git checkout -q main

SEEN=$(mktemp)
pushed=0; skipped=0
PY="$(command -v python3 || command -v python)"
OKS=$("$PY" -c "import json;d=json.load(open('$PORTS/_stage2.json'));print('\n'.join(k for k,v in sorted(d.items()) if v.get('ran') and not v.get('crashed') and v.get('decisions',0)>0 and v.get('errors',1)==0))")

for stem in $OKS; do
  stem="${stem%.py}"
  case " $SKIP " in *" $stem "*) echo "SKIP  $stem (deferred)"; skipped=$((skipped+1)); continue;; esac
  h=$(shasum "$PORTS/$stem.py" | awk '{print $1}')
  if grep -q "^$h " "$SEEN"; then echo "SKIP  $stem (dup of $(grep "^$h " "$SEEN" | awk '{print $2}'))"; skipped=$((skipped+1)); continue; fi
  echo "$h $stem" >> "$SEEN"
  branch="human/$(echo "$stem" | sed 's/__/\//')"   # scml2021__team_54 -> human/scml2021/team_54
  git checkout -q main
  git checkout -q -B "$branch"
  cp "$PORTS/$stem.py" scml_agent.py
  git add scml_agent.py
  git -c user.email=player@codeclash.com -c user.name="CodeClash" commit -qm "Import $stem (SCML OneShot ladder)"
  git push -q -f -u origin "$branch" 2>/dev/null
  echo "PUSH  $branch"
  pushed=$((pushed+1))
done
cd "$REPO_ROOT"; rm -rf "$TMP"
echo "=== pushed $pushed, skipped $skipped ==="
