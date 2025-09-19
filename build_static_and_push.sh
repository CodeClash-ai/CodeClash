#!/usr/bin/env bash

set -x
set -euo pipefail

# START AT MAIN REPO ROOT
rm -rf build
echo "Building static site..."
python freeze_viewer.py
echo "Copying README..."
cp codeclash/viewer/_STATIC_README.md build/README.md
echo "Size of build directory:"
du -hs build
echo "Pushing to github..."
cd build
git init
git config user.name "yolo h8cker 93"
git config user.email "yoloh8cker93@codeclash.ai"
git config commit.gpgsign false
git add .
git commit --no-gpg-sign -m "Deploy static site"
git branch -M main
git remote add origin git@github.com:klieret/emagedoc-static-viewer
git push -f origin main
cd ..
rm -rf build
