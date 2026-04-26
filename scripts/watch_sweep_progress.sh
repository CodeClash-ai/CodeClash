#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

RUN_ROOT=""
OPPONENT_ALIAS="gpt-5"
INTERVAL=15
ONCE=0
ALL_TIERS=0

usage() {
  cat <<'EOF'
Usage:
  scripts/watch_sweep_progress.sh [options]

Options:
  --run-root <path>       Explicit sweep log root.
  --opponent-alias <name> Match generated config dirs: *_vs_<name> (default: gpt-5).
  --all-tiers             Show default, low, medium, and high tiers together.
  --interval <seconds>    Refresh interval (default: 15).
  --once                  Print one snapshot and exit.
  -h, --help              Show help.

Default run-root auto-detection order:
  1) latest logs/new_openai_sweep_*
  2) latest logs/gpt54_vs_gpt53codex_reasoning_*
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-root)
      RUN_ROOT="${2:-}"
      shift 2
      ;;
    --opponent-alias)
      OPPONENT_ALIAS="${2:-}"
      shift 2
      ;;
    --all-tiers)
      ALL_TIERS=1
      shift
      ;;
    --interval)
      INTERVAL="${2:-}"
      shift 2
      ;;
    --once)
      ONCE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "${RUN_ROOT}" ]]; then
  RUN_ROOT="$(
    ls -td \
      "${REPO_ROOT}"/logs/new_openai_sweep_* \
      "${REPO_ROOT}"/logs/gpt54_vs_gpt53codex_reasoning_* \
      2>/dev/null | head -n 1 || true
  )"
fi

if [[ -z "${RUN_ROOT}" || ! -d "${RUN_ROOT}" ]]; then
  echo "No valid run root found. Pass --run-root explicitly." >&2
  exit 1
fi

if ! [[ "${INTERVAL}" =~ ^[0-9]+$ ]]; then
  echo "--interval must be an integer number of seconds." >&2
  exit 1
fi

print_snapshot() {
  local opponent_alias="$1"
  cd "${REPO_ROOT}"
  uv run python - "${REPO_ROOT}" "${RUN_ROOT}" "${opponent_alias}" <<'PY'
from pathlib import Path
import json
import yaml

from codeclash import CONFIG_DIR
from codeclash.utils.yaml_utils import resolve_includes

repo = Path(__import__("sys").argv[1])
run_root = Path(__import__("sys").argv[2])
opponent_alias = __import__("sys").argv[3]

def normalize_players(players: list[str], opponent_alias: str) -> list[str]:
    """Normalize known stale aliases in generated configs/metadata for matching."""
    suffix = None
    prefix = "gpt-5.3-codex-"
    if opponent_alias.startswith(prefix):
        suffix = opponent_alias[len(prefix):]

    normalized = []
    for player in players:
        if player == "gpt5" and suffix:
            normalized.append(f"gpt-5.4-{suffix}")
        else:
            normalized.append(player)
    return sorted(normalized)

cfgs = sorted((repo / "configs" / "generated").glob(f"*_vs_{opponent_alias}/*.yaml"))
print(f"RUN_ROOT: {run_root}")
print(f"TOTAL CONFIGS: {len(cfgs)}")

metas = []
for m in run_root.rglob("metadata.json"):
    try:
        md = json.loads(m.read_text())
        cc = md.get("config", {})
        metas.append(
            (
                cc.get("game", {}).get("name"),
                normalize_players([p.get("name") for p in cc.get("players", [])], opponent_alias),
                md,
                m,
            )
        )
    except Exception:
        pass

done = partial = pending = 0
for c in cfgs:
    cfg = yaml.safe_load(resolve_includes(c.read_text(), base_dir=CONFIG_DIR))
    game = cfg["game"]["name"]
    rounds = int(cfg["tournament"]["rounds"])
    players = normalize_players([p["name"] for p in cfg["players"]], opponent_alias)

    # Pick newest metadata for this game+player pair (important when retries create multiple folders).
    hit = None
    newest_mtime = -1.0
    for g, p, md, meta_path in metas:
        if g != game or p != players:
            continue
        ts = float((md.get("timing") or {}).get("start_time", 0.0))
        if ts < 1.0:
            ts = meta_path.stat().st_mtime
        if ts >= newest_mtime:
            newest_mtime = ts
            hit = md

    if not hit:
        st = "PENDING"
        pending += 1
    else:
        rs = hit.get("round_stats", {})
        st = "DONE" if len(rs) >= rounds + 1 else "PARTIAL"
        done += st == "DONE"
        partial += st == "PARTIAL"

    print(f"{st:7} {c.name}")

print(f"\nSUMMARY done={done} partial={partial} pending={pending}")
PY
}

print_all_tiers() {
  local tier
  for tier in default low medium high; do
    echo "===== ${tier} ====="
    print_snapshot "gpt-5.3-codex-${tier}"
    echo
  done
}

if [[ "${ONCE}" -eq 1 ]]; then
  if [[ "${ALL_TIERS}" -eq 1 ]]; then
    print_all_tiers
  else
    print_snapshot "${OPPONENT_ALIAS}"
  fi
  exit 0
fi

while true; do
  clear
  echo "Sweep Progress Monitor ($(date))"
  echo
  if [[ "${ALL_TIERS}" -eq 1 ]]; then
    print_all_tiers
  else
    print_snapshot "${OPPONENT_ALIAS}"
  fi
  sleep "${INTERVAL}"
done
