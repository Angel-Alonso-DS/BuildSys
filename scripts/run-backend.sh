#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../apps/api"
PYTHONPATH=src exec python3 -m buildsys_api.app
