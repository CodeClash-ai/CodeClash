#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PLAYER_MODEL="openai/gpt-5.4"
OPPONENT_MODEL="openai/gpt-5.3-codex"
RUN_ROOT="${REPO_ROOT}/logs/gpt54_vs_gpt53codex_reasoning_$(date +%Y%m%d_%H%M%S)"
MAX_CONFIG_RETRIES=2
CONTINUE_ON_ERROR=0
OPEN_VIEWER=0
RESUME=0
DRY_RUN=0
PARALLEL=0
MAX_PARALLEL=4

usage() {
    cat <<'EOF'
Usage:
  scripts/run_gpt54_vs_gpt53codex_reasoning.sh [options]

Description:
  Runs direct head-to-head benchmark sweeps for openai/gpt-5.4 vs openai/gpt-5.3-codex
  across four effort tiers in one shared log root:
    - default
    - low
    - medium
    - high

Options:
  --run-root <path>         Set custom logs root for this batch.
  --max-config-retries <n>  Retry each failed arena config up to n times (default: 2).
  --continue-on-error       Continue to remaining configs/tiers when one fails.
  --resume                  Skip already-completed per-arena configs in an existing --run-root.
  --parallel                Run tiers in parallel.
  --max-parallel <n>        Maximum concurrent tiers when --parallel is set (default: 4).
  --viewer                  Launch viewer after the eval pipeline.
  --dry-run                 Print commands without running them.
  -h, --help                Show help.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --run-root)
            RUN_ROOT="${2:-}"
            shift 2
            ;;
        --max-config-retries)
            MAX_CONFIG_RETRIES="${2:-}"
            shift 2
            ;;
        --continue-on-error)
            CONTINUE_ON_ERROR=1
            shift
            ;;
        --resume)
            RESUME=1
            shift
            ;;
        --parallel)
            PARALLEL=1
            shift
            ;;
        --max-parallel)
            MAX_PARALLEL="${2:-}"
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

if ! [[ "${MAX_CONFIG_RETRIES}" =~ ^[0-9]+$ ]]; then
    echo "Error: --max-config-retries must be a non-negative integer, got '${MAX_CONFIG_RETRIES}'" >&2
    exit 1
fi

if ! [[ "${MAX_PARALLEL}" =~ ^[0-9]+$ ]] || [[ "${MAX_PARALLEL}" -lt 1 ]]; then
    echo "Error: --max-parallel must be a positive integer, got '${MAX_PARALLEL}'" >&2
    exit 1
fi

if [[ ! -x "${REPO_ROOT}/scripts/run_openai_model_benchmarks.sh" ]]; then
    echo "Missing or non-executable: ${REPO_ROOT}/scripts/run_openai_model_benchmarks.sh" >&2
    exit 1
fi

if [[ ! -x "${REPO_ROOT}/scripts/run_eval_pipeline.sh" ]]; then
    echo "Missing or non-executable: ${REPO_ROOT}/scripts/run_eval_pipeline.sh" >&2
    exit 1
fi

mkdir -p "${RUN_ROOT}"

common_args=(
    --model "${PLAYER_MODEL}"
    --opponent "${OPPONENT_MODEL}"
    --log-dir "${RUN_ROOT}"
    --max-config-retries "${MAX_CONFIG_RETRIES}"
)

if [[ ${CONTINUE_ON_ERROR} -eq 1 ]]; then
    common_args+=(--continue-on-error)
fi

if [[ ${RESUME} -eq 1 ]]; then
    common_args+=(--resume)
fi

run_tier() {
    local tier="$1"
    local player_alias="gpt-5.4-${tier}"
    local opponent_alias="gpt-5.3-codex-${tier}"
    local -a args=("${common_args[@]}" --alias "${player_alias}" --opponent-alias "${opponent_alias}")

    if [[ "${tier}" != "default" ]]; then
        args+=(--player-reasoning-effort "${tier}" --opponent-reasoning-effort "${tier}")
    fi

    echo "==> Running tier: ${tier}"
    "${REPO_ROOT}/scripts/run_openai_model_benchmarks.sh" "${args[@]}"
}

echo "==> Repo root: ${REPO_ROOT}"
echo "==> Run root: ${RUN_ROOT}"
echo "==> Player model: ${PLAYER_MODEL}"
echo "==> Opponent model: ${OPPONENT_MODEL}"
echo "==> Tiers: default, low, medium, high"
echo "==> Continue on error: ${CONTINUE_ON_ERROR}"
echo "==> Resume: ${RESUME}"
echo "==> Parallel tiers: ${PARALLEL}"
echo "==> Max parallel tiers: ${MAX_PARALLEL}"
echo "==> Max config retries: ${MAX_CONFIG_RETRIES}"

if [[ ${DRY_RUN} -eq 1 ]]; then
    for tier in default low medium high; do
        if [[ "${tier}" == "default" ]]; then
            echo "${REPO_ROOT}/scripts/run_openai_model_benchmarks.sh ${common_args[*]} --alias gpt-5.4-default --opponent-alias gpt-5.3-codex-default"
        else
            echo "${REPO_ROOT}/scripts/run_openai_model_benchmarks.sh ${common_args[*]} --alias gpt-5.4-${tier} --opponent-alias gpt-5.3-codex-${tier} --player-reasoning-effort ${tier} --opponent-reasoning-effort ${tier}"
        fi
    done
    if [[ ${OPEN_VIEWER} -eq 1 ]]; then
        echo "${REPO_ROOT}/scripts/run_eval_pipeline.sh --log-dir ${RUN_ROOT} --viewer"
    else
        echo "${REPO_ROOT}/scripts/run_eval_pipeline.sh --log-dir ${RUN_ROOT}"
    fi
    exit 0
fi

if [[ ${PARALLEL} -eq 1 ]]; then
    declare -a PIDS=()
    declare -a PID_TIERS=()
    declare -i FAILURE_COUNT=0

    wait_for_one() {
        local pid="${PIDS[0]}"
        local tier="${PID_TIERS[0]}"
        local status=0

        if ! wait "${pid}"; then
            status=$?
            echo "==> Tier failed: ${tier} (exit ${status})" >&2
            FAILURE_COUNT+=1
            if [[ ${CONTINUE_ON_ERROR} -ne 1 ]]; then
                echo "==> Stopping due to tier failure and --continue-on-error not set." >&2
                exit "${status}"
            fi
        else
            echo "==> Tier finished: ${tier}"
        fi

        PIDS=("${PIDS[@]:1}")
        PID_TIERS=("${PID_TIERS[@]:1}")
    }

    for tier in default low medium high; do
        run_tier "${tier}" &
        PIDS+=("$!")
        PID_TIERS+=("${tier}")
        if [[ ${#PIDS[@]} -ge ${MAX_PARALLEL} ]]; then
            wait_for_one
        fi
    done

    while [[ ${#PIDS[@]} -gt 0 ]]; do
        wait_for_one
    done

    if [[ ${FAILURE_COUNT} -gt 0 ]]; then
        echo "==> ${FAILURE_COUNT} tier(s) failed." >&2
    fi
else
    run_tier default
    run_tier low
    run_tier medium
    run_tier high
fi

if [[ ${OPEN_VIEWER} -eq 1 ]]; then
    "${REPO_ROOT}/scripts/run_eval_pipeline.sh" --log-dir "${RUN_ROOT}" --viewer
else
    "${REPO_ROOT}/scripts/run_eval_pipeline.sh" --log-dir "${RUN_ROOT}"
fi
