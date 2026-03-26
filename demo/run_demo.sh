#!/usr/bin/env bash
set -euo pipefail
echo "CARD Demo"
echo "========="
cd "$(dirname "$0")/.."
python demo/run_demo.py "$@"
