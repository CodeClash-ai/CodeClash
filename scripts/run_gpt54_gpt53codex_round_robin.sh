#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

RUN_ROOT="${REPO_ROOT}/logs/gpt54_gpt53codex_round_robin_$(date +%Y%m%d_%H%M%S)"
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
  scripts/run_gpt54_gpt53codex_round_robin.sh [options]

Description:
  Runs a full round robin across 8 variants:
    - gpt-5.4-default
    - gpt-5.4-low
    - gpt-5.4-medium
    - gpt-5.4-high
    - gpt-5.3-codex-default
    - gpt-5.3-codex-low
    - gpt-5.3-codex-medium
    - gpt-5.3-codex-high

  This creates one connected match graph so Elo is meaningful across all 8 variants.

Options:
  --run-root <path>         Set custom logs root for this batch.
  --max-config-retries <n>  Retry each failed arena config up to n times (default: 2).
  --continue-on-error       Continue after a failed pairing.
  --resume                  Skip already-completed per-arena configs in an existing --run-root.
  --parallel                Run pairings in parallel.
  --max-parallel <n>        Maximum concurrent pairings when --parallel is set (default: 4).
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

declare -a VARIANT_KEYS=(
    "gpt-5.4-default"
    "gpt-5.4-low"
    "gpt-5.4-medium"
    "gpt-5.4-high"
    "gpt-5.3-codex-default"
    "gpt-5.3-codex-low"
    "gpt-5.3-codex-medium"
    "gpt-5.3-codex-high"
)

variant_model() {
    case "$1" in
        gpt-5.4-*) echo "openai/gpt-5.4" ;;
        gpt-5.3-codex-*) echo "openai/gpt-5.3-codex" ;;
        *) echo "Unknown variant: $1" >&2; exit 1 ;;
    esac
}

variant_effort() {
    case "$1" in
        *-default) echo "" ;;
        *-low) echo "low" ;;
        *-medium) echo "medium" ;;
        *-high) echo "high" ;;
        *) echo "Unknown variant: $1" >&2; exit 1 ;;
    esac
}

common_args=(
    --log-dir "${RUN_ROOT}"
    --max-config-retries "${MAX_CONFIG_RETRIES}"
)

if [[ ${CONTINUE_ON_ERROR} -eq 1 ]]; then
    common_args+=(--continue-on-error)
fi

if [[ ${RESUME} -eq 1 ]]; then
    common_args+=(--resume)
fi

run_pairing() {
    local player_alias="$1"
    local opponent_alias="$2"
    local player_model
    local opponent_model
    local player_effort
    local opponent_effort
    local -a args

    player_model="$(variant_model "${player_alias}")"
    opponent_model="$(variant_model "${opponent_alias}")"
    player_effort="$(variant_effort "${player_alias}")"
    opponent_effort="$(variant_effort "${opponent_alias}")"

    args=(
        "${common_args[@]}"
        --model "${player_model}"
        --alias "${player_alias}"
        --opponent "${opponent_model}"
        --opponent-alias "${opponent_alias}"
    )

    if [[ -n "${player_effort}" ]]; then
        args+=(--player-reasoning-effort "${player_effort}")
    fi
    if [[ -n "${opponent_effort}" ]]; then
        args+=(--opponent-reasoning-effort "${opponent_effort}")
    fi

    echo "==> Pairing: ${player_alias} vs ${opponent_alias}"
    "${REPO_ROOT}/scripts/run_openai_model_benchmarks.sh" "${args[@]}"
}

print_pairing_command() {
    local player_alias="$1"
    local opponent_alias="$2"
    local player_model
    local opponent_model
    local player_effort
    local opponent_effort

    player_model="$(variant_model "${player_alias}")"
    opponent_model="$(variant_model "${opponent_alias}")"
    player_effort="$(variant_effort "${player_alias}")"
    opponent_effort="$(variant_effort "${opponent_alias}")"

    printf "%s --model %s --alias %s --opponent %s --opponent-alias %s --log-dir %s --max-config-retries %s" \
        "${REPO_ROOT}/scripts/run_openai_model_benchmarks.sh" \
        "${player_model}" \
        "${player_alias}" \
        "${opponent_model}" \
        "${opponent_alias}" \
        "${RUN_ROOT}" \
        "${MAX_CONFIG_RETRIES}"

    if [[ ${CONTINUE_ON_ERROR} -eq 1 ]]; then
        printf " --continue-on-error"
    fi
    if [[ ${RESUME} -eq 1 ]]; then
        printf " --resume"
    fi
    if [[ -n "${player_effort}" ]]; then
        printf " --player-reasoning-effort %s" "${player_effort}"
    fi
    if [[ -n "${opponent_effort}" ]]; then
        printf " --opponent-reasoning-effort %s" "${opponent_effort}"
    fi
    printf "\n"
}

declare -a PAIRS=()
for ((i = 0; i < ${#VARIANT_KEYS[@]}; i++)); do
    for ((j = i + 1; j < ${#VARIANT_KEYS[@]}; j++)); do
        PAIRS+=("${VARIANT_KEYS[i]}|${VARIANT_KEYS[j]}")
    done
done

echo "==> Repo root: ${REPO_ROOT}"
echo "==> Run root: ${RUN_ROOT}"
echo "==> Variants: ${#VARIANT_KEYS[@]}"
echo "==> Pairings: ${#PAIRS[@]}"
echo "==> Parallel pairings: ${PARALLEL}"
echo "==> Max parallel pairings: ${MAX_PARALLEL}"
echo "==> Continue on error: ${CONTINUE_ON_ERROR}"
echo "==> Resume: ${RESUME}"
echo "==> Max config retries: ${MAX_CONFIG_RETRIES}"

if [[ ${DRY_RUN} -eq 1 ]]; then
    for pair in "${PAIRS[@]}"; do
        IFS="|" read -r player_alias opponent_alias <<<"${pair}"
        print_pairing_command "${player_alias}" "${opponent_alias}"
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
    declare -a PID_PAIRS=()
    declare -i FAILURE_COUNT=0

    wait_for_one() {
        local pid="${PIDS[0]}"
        local pair="${PID_PAIRS[0]}"
        local status=0

        if ! wait "${pid}"; then
            status=$?
            echo "==> Pairing failed: ${pair} (exit ${status})" >&2
            FAILURE_COUNT+=1
            if [[ ${CONTINUE_ON_ERROR} -ne 1 ]]; then
                echo "==> Stopping due to pairing failure and --continue-on-error not set." >&2
                exit "${status}"
            fi
        else
            echo "==> Pairing finished: ${pair}"
        fi

        PIDS=("${PIDS[@]:1}")
        PID_PAIRS=("${PID_PAIRS[@]:1}")
    }

    for pair in "${PAIRS[@]}"; do
        IFS="|" read -r player_alias opponent_alias <<<"${pair}"
        run_pairing "${player_alias}" "${opponent_alias}" &
        PIDS+=("$!")
        PID_PAIRS+=("${player_alias} vs ${opponent_alias}")
        if [[ ${#PIDS[@]} -ge ${MAX_PARALLEL} ]]; then
            wait_for_one
        fi
    done

    while [[ ${#PIDS[@]} -gt 0 ]]; do
        wait_for_one
    done

    if [[ ${FAILURE_COUNT} -gt 0 ]]; then
        echo "==> ${FAILURE_COUNT} pairing(s) failed." >&2
    fi
else
    for pair in "${PAIRS[@]}"; do
        IFS="|" read -r player_alias opponent_alias <<<"${pair}"
        run_pairing "${player_alias}" "${opponent_alias}"
    done
fi

if [[ ${OPEN_VIEWER} -eq 1 ]]; then
    "${REPO_ROOT}/scripts/run_eval_pipeline.sh" --log-dir "${RUN_ROOT}" --viewer
else
    "${REPO_ROOT}/scripts/run_eval_pipeline.sh" --log-dir "${RUN_ROOT}"
fi
