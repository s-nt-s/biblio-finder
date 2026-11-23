#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$0")"
source .venv/bin/activate
. .env
python server.py 127.0.0.1:8001
