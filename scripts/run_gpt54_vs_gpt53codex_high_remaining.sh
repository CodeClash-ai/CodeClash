#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="/Users/muhtasham/Documents/CodeClash"
RUN_ROOT="${REPO_ROOT}/logs/gpt54_vs_gpt53codex_reasoning_20260308_164105"
CFG_ROOT="${REPO_ROOT}/configs/generated/gpt-5.4-high_vs_gpt-5.3-codex-high"
RUN_SUFFIX="gpt-5.4-high-vs-gpt-5.3-codex-high"

cd "${REPO_ROOT}"

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

mkdir -p "${RUN_ROOT}/quarantine"

find "${RUN_ROOT}" -maxdepth 1 -type d \
  -name 'PvpTournament.Halite.r15.s250.p2.gpt-5.3-codex-high.gpt-5.4-high.gpt-5.4-high-vs-gpt-5.3-codex-high.*' \
  -exec mv {} "${RUN_ROOT}/quarantine"/ \;

uv run python main.py \
  "${CFG_ROOT}/Halite__gpt-5.4-high__gpt-5.3-codex-high__r15__s250.yaml" \
  -o "${RUN_ROOT}" \
  -s "${RUN_SUFFIX}"

uv run python main.py \
  "${CFG_ROOT}/HuskyBench__gpt-5.4-high__gpt-5.3-codex-high__r15__s100.yaml" \
  -o "${RUN_ROOT}" \
  -s "${RUN_SUFFIX}"

uv run python main.py \
  "${CFG_ROOT}/RoboCode__gpt-5.4-high__gpt-5.3-codex-high__r15__s250.yaml" \
  -o "${RUN_ROOT}" \
  -s "${RUN_SUFFIX}"

uv run python main.py \
  "${CFG_ROOT}/RobotRumble__gpt-5.4-high__gpt-5.3-codex-high__r15__s250.yaml" \
  -o "${RUN_ROOT}" \
  -s "${RUN_SUFFIX}"
