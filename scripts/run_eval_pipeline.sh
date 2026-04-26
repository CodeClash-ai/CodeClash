#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

usage() {
    cat <<'EOF'
Usage:
  scripts/run_eval_pipeline.sh --log-dir <path> [--output-dir <path>] [--viewer]

Description:
  Runs post-benchmark analysis pipeline for CodeClash logs:
  1) backfill cost info into metadata
  2) compute win-rate summary
  3) compute Elo rankings + uncertainty outputs
  4) generate win-rate heatmap PDF
  5) render markdown leaderboard table for manual patching
  6) optionally launch local viewer

Arguments:
  --log-dir <path>     Required. Root directory containing tournament logs.
  --output-dir <path>  Optional. Defaults to <log-dir>/analysis.
  --viewer             Optional. Launch viewer at end (blocks until Ctrl+C).
  -h, --help           Show this help.
EOF
}

LOG_DIR=""
OUTPUT_DIR=""
OPEN_VIEWER=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --log-dir)
            LOG_DIR="${2:-}"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="${2:-}"
            shift 2
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

if [[ -z "${LOG_DIR}" ]]; then
    echo "Error: --log-dir is required." >&2
    usage
    exit 1
fi

if [[ ! -d "${LOG_DIR}" ]]; then
    echo "Error: log directory does not exist: ${LOG_DIR}" >&2
    exit 1
fi

if [[ -z "${OUTPUT_DIR}" ]]; then
    OUTPUT_DIR="${LOG_DIR%/}/analysis"
fi

ELO_OUT="${OUTPUT_DIR%/}/elo"
HEATMAP_OUT="${OUTPUT_DIR%/}/heatmap_win_rates.pdf"
TABLE_OUT="${OUTPUT_DIR%/}/leaderboard_table.md"

mkdir -p "${ELO_OUT}"

echo "==> Repo root: ${REPO_ROOT}"
echo "==> Log dir: ${LOG_DIR}"
echo "==> Output dir: ${OUTPUT_DIR}"

cd "${REPO_ROOT}"

echo "==> Step 1/5: Backfilling cost info into metadata..."
uv run python "${REPO_ROOT}/scripts/include_cost_info_in_metadata.py" "${LOG_DIR}"

echo "==> Step 2/5: Computing win-rate summary..."
uv run python "${REPO_ROOT}/codeclash/analysis/metrics/win_rate.py" -d "${LOG_DIR}"

echo "==> Step 3/5: Computing Elo rankings..."
uv run python "${REPO_ROOT}/codeclash/analysis/metrics/elo.py" \
    -d "${LOG_DIR}" \
    --output-dir "${ELO_OUT}"

echo "==> Step 4/5: Generating win-rate heatmap..."
uv run python "${REPO_ROOT}/codeclash/analysis/viz/heatmap_win_rates.py" \
    -d "${LOG_DIR}" \
    -o "${HEATMAP_OUT}"

echo "==> Step 5/5: Rendering leaderboard table..."
uv run python "${REPO_ROOT}/scripts/print_leaderboard_table.py" \
    --input "${ELO_OUT}/leaderboards.json" \
    --out "${TABLE_OUT}"

echo
echo "Pipeline complete."
echo "Elo outputs: ${ELO_OUT}"
echo "Heatmap: ${HEATMAP_OUT}"
echo "Leaderboard table: ${TABLE_OUT}"

if [[ ${OPEN_VIEWER} -eq 1 ]]; then
    echo "==> Launching viewer (Ctrl+C to stop)..."
    uv run python "${REPO_ROOT}/scripts/run_viewer.py" -d "${LOG_DIR}"
else
    echo "To inspect trajectories: uv run python ${REPO_ROOT}/scripts/run_viewer.py -d ${LOG_DIR}"
fi
