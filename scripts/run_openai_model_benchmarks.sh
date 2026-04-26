#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

usage() {
    cat <<'EOF'
Usage:
  scripts/run_openai_model_benchmarks.sh --model <openai/model-id> [options]

Description:
  Generates configs for one OpenAI model vs a configurable opponent across the standard
  benchmark arenas, runs all tournaments, and optionally runs post-eval analysis.

Required:
  --model <id>               Example: openai/gpt-5.4-pro-2026-03-05

Optional:
  --alias <name>             Player/config alias (default: model basename).
  --opponent <id>            Opponent model id (default: openai/gpt-5).
  --opponent-alias <name>    Opponent display alias in config (default: opponent basename).
  --reasoning-effort <lvl>   Set reasoning_effort for both players (e.g. low|medium|high).
  --player-reasoning-effort <lvl>
                             Set reasoning_effort only for the evaluated model.
  --opponent-reasoning-effort <lvl>
                             Set reasoning_effort only for the opponent model.
  --log-dir <path>           Logs root output dir (default: logs/<alias>_vs_<opponent>_<timestamp>).
  --configs-dir <path>       Generated configs dir (default: configs/generated).
  --resume                   Skip configs that already have a completed run in --log-dir.
  --max-config-retries <n>   Retry each failed config up to n times (default: 2).
  --continue-on-error        Continue to remaining configs even if one fails.
  --post-eval                Run scripts/run_eval_pipeline.sh after runs.
  --viewer                   With --post-eval, also launch viewer at end.
  --dry-run                  Generate configs + print run commands only.
  -h, --help                 Show help.

Notes:
  - This script uses model_class: litellm for both players.
  - It expects OPENAI_API_KEY (and usually GITHUB_TOKEN) in your environment.
EOF
}

MODEL=""
ALIAS=""
OPPONENT="openai/gpt-5"
OPPONENT_ALIAS=""
REASONING_EFFORT=""
PLAYER_REASONING_EFFORT=""
OPPONENT_REASONING_EFFORT=""
LOG_DIR=""
CONFIGS_DIR="${REPO_ROOT}/configs/generated"
RUN_POST_EVAL=0
OPEN_VIEWER=0
DRY_RUN=0
RESUME=0
CONTINUE_ON_ERROR=0
MAX_CONFIG_RETRIES=2

while [[ $# -gt 0 ]]; do
    case "$1" in
        --model)
            MODEL="${2:-}"
            shift 2
            ;;
        --alias)
            ALIAS="${2:-}"
            shift 2
            ;;
        --opponent)
            OPPONENT="${2:-}"
            shift 2
            ;;
        --opponent-alias)
            OPPONENT_ALIAS="${2:-}"
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
        --log-dir)
            LOG_DIR="${2:-}"
            shift 2
            ;;
        --configs-dir)
            CONFIGS_DIR="${2:-}"
            shift 2
            ;;
        --post-eval)
            RUN_POST_EVAL=1
            shift
            ;;
        --resume)
            RESUME=1
            shift
            ;;
        --continue-on-error)
            CONTINUE_ON_ERROR=1
            shift
            ;;
        --max-config-retries)
            MAX_CONFIG_RETRIES="${2:-}"
            shift 2
            ;;
        --viewer)
            OPEN_VIEWER=1
            shift
            ;;
        --dry-run)
            DRY_RUN=1
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

if [[ -z "${MODEL}" ]]; then
    echo "Error: --model is required." >&2
    usage
    exit 1
fi

if ! [[ "${MAX_CONFIG_RETRIES}" =~ ^[0-9]+$ ]]; then
    echo "Error: --max-config-retries must be a non-negative integer, got '${MAX_CONFIG_RETRIES}'" >&2
    exit 1
fi

# Force key source to repo .env so mini-swe-agent global env doesn't silently override.
OPENAI_KEY_FROM_REPO="$(
    uv run python - "${REPO_ROOT}/.env" <<'PY'
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

if [[ -z "${OPENAI_KEY_FROM_REPO}" ]]; then
    echo "Error: OPENAI_API_KEY missing in ${REPO_ROOT}/.env" >&2
    exit 1
fi
export OPENAI_API_KEY="${OPENAI_KEY_FROM_REPO}"
unset OPENAI_KEY_FROM_REPO

uv run python - "${REPO_ROOT}/.env" <<'PY'
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

print(f"==> OPENAI key source forced: {repo_env}")
print(f"==> OPENAI key fingerprint: {fp(env_key)}")
if mini_key and mini_key != repo_key:
    print("==> note: mini-swe-agent global key differs; repo key is forced for this run.")
PY

normalize_model_id() {
    local v="${1#@}"
    if [[ "${v}" == */* ]]; then
        echo "${v}"
    else
        echo "openai/${v}"
    fi
}

# Accept "@openai/gpt-5", "openai/gpt-5", and bare "gpt-5".
MODEL="$(normalize_model_id "${MODEL}")"
OPPONENT="$(normalize_model_id "${OPPONENT}")"

if [[ -n "${REASONING_EFFORT}" ]]; then
    if [[ -z "${PLAYER_REASONING_EFFORT}" ]]; then
        PLAYER_REASONING_EFFORT="${REASONING_EFFORT}"
    fi
    if [[ -z "${OPPONENT_REASONING_EFFORT}" ]]; then
        OPPONENT_REASONING_EFFORT="${REASONING_EFFORT}"
    fi
fi

requires_responses_model_class() {
    local m="$1"
    case "$m" in
        openai/gpt-5.4-pro-2026-03-05) return 0 ;;
        *) return 1 ;;
    esac
}

PLAYER_MODEL_CLASS="litellm"
OPPONENT_MODEL_CLASS="litellm"
RESPONSES_SANITIZED_CLASS="codeclash.agents.litellm_response_sanitized_model.LitellmResponseSanitizedModel"
responses_class_available=0
if uv run python - "${RESPONSES_SANITIZED_CLASS}" <<'PY' >/dev/null 2>&1
import importlib
import sys

class_path = sys.argv[1]
module_name, class_name = class_path.rsplit(".", 1)
mod = importlib.import_module(module_name)
getattr(mod, class_name)
PY
then
    responses_class_available=1
fi
if requires_responses_model_class "${MODEL}"; then
    if [[ ${responses_class_available} -eq 1 ]]; then
        PLAYER_MODEL_CLASS="${RESPONSES_SANITIZED_CLASS}"
    else
        echo "Warning: requested Responses model class '${RESPONSES_SANITIZED_CLASS}' is not importable; falling back to 'litellm'." >&2
    fi
fi
if requires_responses_model_class "${OPPONENT}"; then
    if [[ ${responses_class_available} -eq 1 ]]; then
        OPPONENT_MODEL_CLASS="${RESPONSES_SANITIZED_CLASS}"
    else
        echo "Warning: requested Responses model class '${RESPONSES_SANITIZED_CLASS}' is not importable; falling back to 'litellm'." >&2
    fi
fi

if [[ -z "${ALIAS}" ]]; then
    ALIAS="${MODEL#openai/}"
fi

if [[ -z "${OPPONENT_ALIAS}" ]]; then
    OPPONENT_ALIAS="${OPPONENT#openai/}"
fi

SAFE_ALIAS="${ALIAS//\//-}"
SAFE_ALIAS="${SAFE_ALIAS//@/}"
SAFE_OPPONENT_ALIAS="${OPPONENT_ALIAS//\//-}"
SAFE_OPPONENT_ALIAS="${SAFE_OPPONENT_ALIAS//@/}"
RUN_SUFFIX="${SAFE_ALIAS}-vs-${SAFE_OPPONENT_ALIAS}"

if [[ -z "${LOG_DIR}" ]]; then
    TS="$(date +%Y%m%d_%H%M%S)"
    LOG_DIR="${REPO_ROOT}/logs/${SAFE_ALIAS}_vs_${SAFE_OPPONENT_ALIAS}_${TS}"
fi

RUN_CONFIG_DIR="${CONFIGS_DIR%/}/${SAFE_ALIAS}_vs_${SAFE_OPPONENT_ALIAS}"
mkdir -p "${RUN_CONFIG_DIR}" "${LOG_DIR}"

declare -a TEMPLATES=(
    "${REPO_ROOT}/configs/main/BattleSnake__gpt-5__o3__r15__s1000.yaml"
    "${REPO_ROOT}/configs/main/CoreWar__gpt-5__o3__r15__s1000.yaml"
    "${REPO_ROOT}/configs/main/Halite__gpt-5__o3__r15__s250.yaml"
    "${REPO_ROOT}/configs/main/RoboCode__gpt-5__o3__r15__s250.yaml"
    "${REPO_ROOT}/configs/main/RobotRumble__gpt-5__o3__r15__s250.yaml"
    "${REPO_ROOT}/configs/main/HuskyBench__gpt-5__o3__r15__s100.yaml"
)

for tpl in "${TEMPLATES[@]}"; do
    if [[ ! -f "${tpl}" ]]; then
        echo "Error: Missing template config: ${tpl}" >&2
        exit 1
    fi
done

declare -a GENERATED_CONFIGS=()
for tpl in "${TEMPLATES[@]}"; do
    base_name="$(basename "${tpl}")"
    out_name="${base_name/__gpt-5__o3__/__${SAFE_ALIAS}__${SAFE_OPPONENT_ALIAS}__}"
    out_path="${RUN_CONFIG_DIR}/${out_name}"

    uv run python - "${tpl}" "${out_path}" "${MODEL}" "${ALIAS}" "${OPPONENT}" "${OPPONENT_ALIAS}" "${PLAYER_MODEL_CLASS}" "${OPPONENT_MODEL_CLASS}" "${PLAYER_REASONING_EFFORT}" "${OPPONENT_REASONING_EFFORT}" <<'PY'
from pathlib import Path
import re
import sys

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
model = sys.argv[3]
alias = sys.argv[4]
opponent = sys.argv[5]
opponent_alias = sys.argv[6]
player_model_class = sys.argv[7]
opponent_model_class = sys.argv[8]
player_reasoning_effort = sys.argv[9]
opponent_reasoning_effort = sys.argv[10]

text = src.read_text()

# First player name in template is gpt-5.
text = re.sub(r"(?m)^  name: gpt-5$", f"  name: {alias}", text, count=1)
# Second player name in template is o3.
text = re.sub(r"(?m)^  name: o3$", f"  name: {opponent_alias}", text, count=1)

# Convert model IDs from Portkey-style "@openai/*" to LiteLLM "openai/*".
text = text.replace("model_name: '@openai/gpt-5'", f"model_name: '{model}'")
text = text.replace("model_name: '@openai/o3'", f"model_name: '{opponent}'")

# Base class for generated configs.
text = text.replace("model_class: portkey", "model_class: litellm")

# The template has exactly two player blocks; map class by player order.
class_lines = [i for i, line in enumerate(text.splitlines()) if line.strip() == "model_class: litellm"]
lines = text.splitlines()
if len(class_lines) >= 1 and player_model_class != "litellm":
    lines[class_lines[0]] = re.sub(r"litellm$", player_model_class, lines[class_lines[0]])
if len(class_lines) >= 2 and opponent_model_class != "litellm":
    lines[class_lines[1]] = re.sub(r"litellm$", opponent_model_class, lines[class_lines[1]])

# Inject per-player reasoning effort as model_kwargs when requested.
offset = 0
targets = [
    (class_lines[0] if len(class_lines) >= 1 else None, player_reasoning_effort),
    (class_lines[1] if len(class_lines) >= 2 else None, opponent_reasoning_effort),
]
for class_idx, effort in targets:
    if class_idx is None or not effort:
        continue
    idx = class_idx + offset
    indent = re.match(r"^(\s*)", lines[idx]).group(1)
    effort_escaped = effort.replace("'", "''")
    lines[idx + 1 : idx + 1] = [
        f"{indent}model_kwargs:",
        f"{indent}  reasoning_effort: '{effort_escaped}'",
    ]
    offset += 2

text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")

dst.write_text(text)
PY

    GENERATED_CONFIGS+=("${out_path}")
done

echo "==> Model: ${MODEL}"
echo "==> Alias: ${ALIAS}"
echo "==> Opponent: ${OPPONENT}"
echo "==> Opponent alias: ${OPPONENT_ALIAS}"
echo "==> Player model class: ${PLAYER_MODEL_CLASS}"
echo "==> Opponent model class: ${OPPONENT_MODEL_CLASS}"
echo "==> Player reasoning_effort: ${PLAYER_REASONING_EFFORT:-<default>}"
echo "==> Opponent reasoning_effort: ${OPPONENT_REASONING_EFFORT:-<default>}"
echo "==> Generated configs dir: ${RUN_CONFIG_DIR}"
echo "==> Logs dir: ${LOG_DIR}"
echo "==> Resume: ${RESUME}"
echo "==> Continue on error: ${CONTINUE_ON_ERROR}"
echo "==> Max config retries: ${MAX_CONFIG_RETRIES}"
echo "==> Configs:"
printf '  - %s\n' "${GENERATED_CONFIGS[@]}"

if [[ ${DRY_RUN} -eq 1 ]]; then
    echo
    echo "Dry-run only. Commands that would run:"
    for cfg in "${GENERATED_CONFIGS[@]}"; do
        echo "uv run python ${REPO_ROOT}/main.py ${cfg} -o ${LOG_DIR} -s ${RUN_SUFFIX}"
    done
    if [[ ${RUN_POST_EVAL} -eq 1 ]]; then
        if [[ ${OPEN_VIEWER} -eq 1 ]]; then
            echo "${REPO_ROOT}/scripts/run_eval_pipeline.sh --log-dir ${LOG_DIR} --viewer"
        else
            echo "${REPO_ROOT}/scripts/run_eval_pipeline.sh --log-dir ${LOG_DIR}"
        fi
    fi
    exit 0
fi

cd "${REPO_ROOT}"

is_config_completed() {
    local cfg_path="$1"
    local log_dir="$2"
    uv run python - "$cfg_path" "$log_dir" <<'PY'
import json
import sys
from pathlib import Path

import yaml

cfg_path = Path(sys.argv[1])
log_dir = Path(sys.argv[2])

cfg = yaml.safe_load(cfg_path.read_text())
cfg_game = cfg["game"]["name"]
cfg_rounds = int(cfg["tournament"]["rounds"])
cfg_players = sorted(p["name"] for p in cfg["players"])
expected_round_keys = {str(i) for i in range(cfg_rounds + 1)}

for meta_path in log_dir.rglob("metadata.json"):
    try:
        meta = json.loads(meta_path.read_text())
    except Exception:
        continue
    conf = meta.get("config", {})
    game = conf.get("game", {}).get("name")
    players = sorted(p.get("name") for p in conf.get("players", []))
    if game != cfg_game or players != cfg_players:
        continue
    round_stats = meta.get("round_stats", {})
    if expected_round_keys.issubset(set(round_stats.keys())):
        print(meta_path)
        sys.exit(0)

sys.exit(1)
PY
}

declare -a COMPLETED_CONFIGS=()
declare -a SKIPPED_CONFIGS=()
declare -a FAILED_CONFIGS=()

for cfg in "${GENERATED_CONFIGS[@]}"; do
    echo
    echo "==> Running benchmark: ${cfg}"

    if [[ ${RESUME} -eq 1 ]]; then
        if completed_path="$(is_config_completed "${cfg}" "${LOG_DIR}" 2>/dev/null)"; then
            echo "    skipping (resume): found completed run at ${completed_path}"
            SKIPPED_CONFIGS+=("${cfg}")
            continue
        fi
    fi

    max_attempts=$((MAX_CONFIG_RETRIES + 1))
    attempt=1
    ran_ok=0
    while [[ ${attempt} -le ${max_attempts} ]]; do
        echo "    attempt ${attempt}/${max_attempts}"
        if uv run python "${REPO_ROOT}/main.py" "${cfg}" -o "${LOG_DIR}" -s "${RUN_SUFFIX}"; then
            ran_ok=1
            break
        fi
        if [[ ${attempt} -lt ${max_attempts} ]]; then
            sleep_s=$((15 * (2 ** (attempt - 1))))
            echo "    failed attempt ${attempt}; retrying in ${sleep_s}s..."
            sleep "${sleep_s}"
        fi
        attempt=$((attempt + 1))
    done

    if [[ ${ran_ok} -eq 1 ]]; then
        COMPLETED_CONFIGS+=("${cfg}")
        continue
    fi

    FAILED_CONFIGS+=("${cfg}")
    if [[ ${CONTINUE_ON_ERROR} -eq 0 ]]; then
        echo "Error: benchmark failed and --continue-on-error is not set." >&2
        exit 1
    fi
done

echo
echo "==> Run summary"
echo "Completed: ${#COMPLETED_CONFIGS[@]}"
echo "Skipped (resume): ${#SKIPPED_CONFIGS[@]}"
echo "Failed: ${#FAILED_CONFIGS[@]}"
if [[ ${#FAILED_CONFIGS[@]} -gt 0 ]]; then
    printf '  - %s\n' "${FAILED_CONFIGS[@]}"
fi

if [[ ${RUN_POST_EVAL} -eq 1 ]]; then
    echo
    echo "==> Running post-eval pipeline..."
    if [[ ${OPEN_VIEWER} -eq 1 ]]; then
        "${REPO_ROOT}/scripts/run_eval_pipeline.sh" --log-dir "${LOG_DIR}" --viewer
    else
        "${REPO_ROOT}/scripts/run_eval_pipeline.sh" --log-dir "${LOG_DIR}"
    fi
fi

echo
echo "Done."
echo "Logs: ${LOG_DIR}"
echo "Generated configs: ${RUN_CONFIG_DIR}"
