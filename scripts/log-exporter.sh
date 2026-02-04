#!/bin/sh
set -eu

LOG_DIR="/logs"
CONTAINERS="eufy-ws eufy-to-n8n caddy n8n test"

mkdir -p "$LOG_DIR"

tail_one() {
  name="$1"
  log_file="$LOG_DIR/${name}.log"

  echo "==== $(date -Iseconds) start tailing ${name} ====" >> "$log_file"

  while true; do
    if docker inspect "$name" >/dev/null 2>&1; then
      # Start from "now" to avoid re-dumping old logs on reconnect.
      docker logs --since 1s -f "$name" >> "$log_file" 2>&1 || true
    else
      echo "==== $(date -Iseconds) waiting for ${name} ====" >> "$log_file"
    fi
    sleep 2
  done
}

for name in $CONTAINERS; do
  tail_one "$name" &
done

wait
