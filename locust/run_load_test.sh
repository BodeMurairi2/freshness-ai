#!/usr/bin/env bash
# Runs the Locust flood test without the web page; the report lands in locust/results/locust_rapport_<timestamp>.csv
# Usage (from the repo root):
#   bash locust/run_load_test.sh USERS [RUN_TIME] [SPAWN_RATE] [HOST]
#   bash locust/run_load_test.sh 50                 # 50 users for 3 minutes
#   bash locust/run_load_test.sh 100 5m 10          # 100 users for 5 minutes, 10 new users per second

set -euo pipefail

USERS="${1:?give the number of users, e.g. bash locust/run_load_test.sh 50}"
RUN_TIME="${2:-3m}"
SPAWN_RATE="${3:-5}"
HOST="${4:-https://api.freshness.bodemurairi.me}"

locust -f locust/locustfile.py \
    --host "$HOST" \
    --headless \
    --users "$USERS" \
    --spawn-rate "$SPAWN_RATE" \
    --run-time "$RUN_TIME" \
    --only-summary
