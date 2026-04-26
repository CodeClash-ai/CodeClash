#!/usr/bin/env bash

set -euo pipefail

REPO="/Users/muhtasham/Documents/CodeClash"
MODELS=(
  "openai/gpt-5.4"
  "openai/gpt-5.3-codex"
)
OPPONENT="openai/gpt-5"

RUN_ROOT="$REPO/logs/new_openai_sweep_$(date +%Y%m%d_%H%M%S)"
CHECK_ONLY=0
PUSH_DIFFS=0
OPEN_VIEWER=0
RESUME=0
CONTINUE_ON_ERROR=0
MAX_CONFIG_RETRIES=2
REASONING_EFFORT=""
PLAYER_REASONING_EFFORT=""
OPPONENT_REASONING_EFFORT=""

usage() {
  cat <<'EOF'
Usage:
  scripts/run_openai_sweep.sh [options]

Options:
  --run-root <path>   Set custom logs root for this sweep.
  --opponent <id>     Opponent baseline model (default: openai/gpt-5).
  --reasoning-effort <lvl>
                      Set reasoning_effort for both players (e.g. low|medium|high).
  --player-reasoning-effort <lvl>
                      Set reasoning_effort for evaluated models only.
  --opponent-reasoning-effort <lvl>
                      Set reasoning_effort for opponent only.
  --check-only        Run preflight checks + dry runs only, then exit.
  --resume            Skip already-completed per-arena configs in an existing --run-root.
  --max-config-retries <n>
                      Retry each failed arena config up to n times (default: 2).
  --continue-on-error Continue with other configs/models when a config fails.
  --push-diffs        After eval, push per-tournament code diffs to arena repos.
  --viewer            Launch local viewer at end of pipeline.
  -h, --help          Show help.

What this script does:
  1) Preflight checks:
     - local scripts/dependencies
     - LiteLLM support for:
       openai/gpt-5.4
       openai/gpt-5.3-codex
       and opponent baseline model
     - dry-run config generation for each model
  2) Full benchmark runs for all listed models (all standard arenas vs chosen opponent)
  3) Combined post-eval pipeline over one shared run root
  4) Optional diff-branch push to CodeClash arena repos
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-root)
      RUN_ROOT="${2:-}"
      shift 2
      ;;
    --opponent)
      OPPONENT="${2:-}"
      shift 2
      ;;
    --reasoning-effort)
      REASONING_EFFORT="${2:-}"
      shift 2
      ;;
    --player-reasoning-effort)
      PLAYER_REASONING_EFFORT="${2:-}"
      shift 2
      ;;
    --opponent-reasoning-effort)
      OPPONENT_REASONING_EFFORT="${2:-}"
      shift 2
      ;;
    --check-only)
      CHECK_ONLY=1
      shift
      ;;
    --resume)
      RESUME=1
      shift
      ;;
    --max-config-retries)
      MAX_CONFIG_RETRIES="${2:-}"
      shift 2
      ;;
    --continue-on-error)
      CONTINUE_ON_ERROR=1
      shift
      ;;
    --push-diffs)
      PUSH_DIFFS=1
      shift
      ;;
    --viewer)
      OPEN_VIEWER=1
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

if ! [[ "${MAX_CONFIG_RETRIES}" =~ ^[0-9]+$ ]]; then
  echo "Error: --max-config-retries must be a non-negative integer, got '${MAX_CONFIG_RETRIES}'" >&2
  exit 1
fi

normalize_model_id() {
  local v="${1#@}"
  if [[ "${v}" == */* ]]; then
    echo "${v}"
  else
    echo "openai/${v}"
  fi
}

OPPONENT="$(normalize_model_id "${OPPONENT}")"

if [[ -n "${REASONING_EFFORT}" ]]; then
  if [[ -z "${PLAYER_REASONING_EFFORT}" ]]; then
    PLAYER_REASONING_EFFORT="${REASONING_EFFORT}"
  fi
  if [[ -z "${OPPONENT_REASONING_EFFORT}" ]]; then
    OPPONENT_REASONING_EFFORT="${REASONING_EFFORT}"
  fi
fi

COMMON_BENCH_ARGS=(--opponent "$OPPONENT" --max-config-retries "$MAX_CONFIG_RETRIES")
if [[ "$RESUME" -eq 1 ]]; then
  COMMON_BENCH_ARGS+=(--resume)
fi
if [[ "$CONTINUE_ON_ERROR" -eq 1 ]]; then
  COMMON_BENCH_ARGS+=(--continue-on-error)
fi
if [[ -n "${PLAYER_REASONING_EFFORT}" ]]; then
  COMMON_BENCH_ARGS+=(--player-reasoning-effort "$PLAYER_REASONING_EFFORT")
fi
if [[ -n "${OPPONENT_REASONING_EFFORT}" ]]; then
  COMMON_BENCH_ARGS+=(--opponent-reasoning-effort "$OPPONENT_REASONING_EFFORT")
fi

if [[ ! -d "$REPO" ]]; then
  echo "Repo not found: $REPO" >&2
  exit 1
fi

if [[ ! -x "$REPO/scripts/run_openai_model_benchmarks.sh" ]]; then
  echo "Missing or non-executable: $REPO/scripts/run_openai_model_benchmarks.sh" >&2
  exit 1
fi

if [[ ! -x "$REPO/scripts/run_eval_pipeline.sh" ]]; then
  echo "Missing or non-executable: $REPO/scripts/run_eval_pipeline.sh" >&2
  exit 1
fi

if [[ ! -f "$REPO/scripts/push_log_to_gh.py" ]]; then
  echo "Missing: $REPO/scripts/push_log_to_gh.py" >&2
  exit 1
fi

mkdir -p "$RUN_ROOT"

cd "$REPO"

echo "==> Auth preflight: forcing OPENAI key from repo .env..."
OPENAI_KEY_FROM_REPO="$(
  uv run python - "$REPO/.env" <<'PY'
import sys
from pathlib import Path
from dotenv import dotenv_values

env_path = Path(sys.argv[1])
if not env_path.exists():
    raise SystemExit(2)
val = dotenv_values(env_path).get("OPENAI_API_KEY", "")
print(val or "")
PY
)"

if [[ -z "$OPENAI_KEY_FROM_REPO" ]]; then
  echo "Error: OPENAI_API_KEY missing in $REPO/.env" >&2
  exit 1
fi
export OPENAI_API_KEY="$OPENAI_KEY_FROM_REPO"
unset OPENAI_KEY_FROM_REPO

uv run python - "$REPO/.env" <<'PY'
import hashlib
import os
import sys
from pathlib import Path
from dotenv import dotenv_values

def fp(v: str) -> str:
    return f"len={len(v)} sha256[:10]={hashlib.sha256(v.encode()).hexdigest()[:10]} tail={v[-4:]}"

repo_env = Path(sys.argv[1])
repo_key = dotenv_values(repo_env).get("OPENAI_API_KEY", "")
env_key = os.environ.get("OPENAI_API_KEY", "")
mini_env = Path.home() / "Library/Application Support/mini-swe-agent/.env"
mini_key = dotenv_values(mini_env).get("OPENAI_API_KEY", "") if mini_env.exists() else ""

print(f"  source: {repo_env}")
print(f"  active OPENAI_API_KEY: {fp(env_key)}")
print(f"  repo   OPENAI_API_KEY: {fp(repo_key)}")
if mini_key:
    print(f"  mini   OPENAI_API_KEY: {fp(mini_key)}")
    if mini_key != repo_key:
        print("  note: mini-swe-agent global key differs; repo key is forced for this run.")
PY

echo "==> Sweep run root: $RUN_ROOT"
echo "==> Models:"
printf '  - %s\n' "${MODELS[@]}"
echo "==> Opponent baseline: $OPPONENT"
echo "==> Player reasoning_effort: ${PLAYER_REASONING_EFFORT:-<default>}"
echo "==> Opponent reasoning_effort: ${OPPONENT_REASONING_EFFORT:-<default>}"

echo
echo "==> Preflight 1/3: LiteLLM model support checks..."
uv run python - "$OPPONENT" <<'PY'
import sys
from importlib.metadata import version
import litellm

opponent = sys.argv[1]
models = [
    "openai/gpt-5.4",
    "openai/gpt-5.3-codex",
    opponent,
]

print(f"litellm_version={version('litellm')}")
ok = True
for m in models:
    print(f"\nMODEL {m}")
    try:
        print("  provider:", litellm.get_llm_provider(model=m))
    except Exception as e:
        ok = False
        print(f"  provider_error: {type(e).__name__}: {e}")
    try:
        info = litellm.get_model_info(model=m)
        print(
            "  model_info:",
            {
                "max_input_tokens": info.get("max_input_tokens"),
                "max_output_tokens": info.get("max_output_tokens"),
                "supports_function_calling": info.get("supports_function_calling"),
            },
        )
    except Exception as e:
        ok = False
        print(f"  model_info_error: {type(e).__name__}: {e}")

if not ok:
    sys.exit(1)
PY

echo
echo "==> Preflight 2/3: Dry-run config generation checks..."
for MODEL in "${MODELS[@]}"; do
  echo "  -> $MODEL"
  "$REPO/scripts/run_openai_model_benchmarks.sh" \
    --model "$MODEL" \
    --log-dir "$RUN_ROOT" \
    "${COMMON_BENCH_ARGS[@]}" \
    --dry-run >/dev/null
done

echo
echo "==> Preflight 3/3: GitHub CLI auth check (needed for optional upload/push flows)..."
gh auth status >/dev/null
echo "  gh auth: OK"

if [[ "$CHECK_ONLY" -eq 1 ]]; then
  echo
  echo "Preflight + dry-run checks passed. Exiting due to --check-only."
  exit 0
fi

echo
echo "==> Running full sweeps..."
for MODEL in "${MODELS[@]}"; do
  echo
  echo "### Running model: $MODEL"
  "$REPO/scripts/run_openai_model_benchmarks.sh" \
    --model "$MODEL" \
    --log-dir "$RUN_ROOT" \
    "${COMMON_BENCH_ARGS[@]}"
done

echo
echo "==> Running combined post-eval pipeline..."
if [[ "$OPEN_VIEWER" -eq 1 ]]; then
  "$REPO/scripts/run_eval_pipeline.sh" --log-dir "$RUN_ROOT" --viewer
else
  "$REPO/scripts/run_eval_pipeline.sh" --log-dir "$RUN_ROOT"
fi

if [[ "$PUSH_DIFFS" -eq 1 ]]; then
  echo
  echo "==> Pushing per-tournament diffs to arena repos..."
  find "$RUN_ROOT" -type f -name metadata.json -print0 \
    | xargs -0 -I{} dirname "{}" \
    | sort -u \
    | while read -r folder; do
        echo "  -> $folder"
        uv run python "$REPO/scripts/push_log_to_gh.py" "$folder"
      done
fi

echo
echo "Done."
echo "Run root: $RUN_ROOT"
echo "Combined leaderboard JSON: $RUN_ROOT/analysis/elo/leaderboards.json"
