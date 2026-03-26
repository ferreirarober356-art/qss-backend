#!/usr/bin/env bash
set -euo pipefail
cd ~/aip_mvp
git status
git add app/api.py requirements.txt 2>/dev/null || true
git commit -m "${1:-backend deploy}" || true
git push origin main
echo "Backend pushed to GitHub. Render should auto-deploy."
