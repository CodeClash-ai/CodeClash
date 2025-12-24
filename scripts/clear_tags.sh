#!/bin/bash

if [ $# -ne 1 ]; then
    echo "Usage: $0 repository-name"
    exit 1
fi
REPO=$1
if [[ ! "$REPO" =~ ^(CoreWar|RobotRumble|RoboCode|HuskyBench|BattleSnake|BattleCode)$ ]]; then
    echo "Repository name must be one of: CoreWar, RobotRumble, RoboCode, HuskyBench, BattleSnake, BattleCode"
    exit 1
fi
git clone git@github.com:CodeClash-ai/$REPO.git
cd $REPO
git ls-remote --tags origin | awk '{print $2}' | sed 's/refs\/tags\///' | xargs -I {} git push origin :refs/tags/{}
cd ..
rm -rf $REPO
