#!/bin/bash

set -euo pipefail

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_SCRIPT="$THIS_DIR/build_and_push_aws.sh"
GAMES_DOCKER_DIR="$THIS_DIR/../../docker"

# AWSCodeClash -> codeclash
"$BUILD_SCRIPT" AWSCodeClash.Dockerfile codeclash "$THIS_DIR"

# Games -> codeclash/<game>
"$BUILD_SCRIPT" "$GAMES_DOCKER_DIR/BattleSnake.Dockerfile" codeclash/battlesnake "$GAMES_DOCKER_DIR"
"$BUILD_SCRIPT" "$GAMES_DOCKER_DIR/BattleCode.Dockerfile" codeclash/battlecode "$GAMES_DOCKER_DIR"
"$BUILD_SCRIPT" "$GAMES_DOCKER_DIR/CoreWar.Dockerfile" codeclash/corewar "$GAMES_DOCKER_DIR"
"$BUILD_SCRIPT" "$GAMES_DOCKER_DIR/DummyGame.Dockerfile" codeclash/dummygame "$GAMES_DOCKER_DIR"
"$BUILD_SCRIPT" "$GAMES_DOCKER_DIR/HuskyBench.Dockerfile" codeclash/huskybench "$GAMES_DOCKER_DIR"
"$BUILD_SCRIPT" "$GAMES_DOCKER_DIR/RoboCode.Dockerfile" codeclash/robocode "$GAMES_DOCKER_DIR"
"$BUILD_SCRIPT" "$GAMES_DOCKER_DIR/RobotRumble.Dockerfile" codeclash/robotrumble "$GAMES_DOCKER_DIR"
