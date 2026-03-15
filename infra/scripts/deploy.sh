#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  deploy.sh --host <host> --user <user> --env-file <path> --config-file <path> --bucket <bucket> [options]

Required:
  --host         Remote host or IP
  --user         SSH user
  --env-file     Local .env file to copy
  --config-file  Local run config JSON to upload to S3
  --bucket       S3 bucket name

Optional:
  --config-key   S3 config key (default: config/run_config.json)
  --app-dir      Remote app dir (default: /opt/argusai)
  --identity     SSH identity file
EOF
}

HOST=""
USER_NAME=""
ENV_FILE=""
CONFIG_FILE=""
BUCKET=""
CONFIG_KEY="config/run_config.json"
APP_DIR="/opt/argusai"
IDENTITY_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2 ;;
    --user) USER_NAME="$2"; shift 2 ;;
    --env-file) ENV_FILE="$2"; shift 2 ;;
    --config-file) CONFIG_FILE="$2"; shift 2 ;;
    --bucket) BUCKET="$2"; shift 2 ;;
    --config-key) CONFIG_KEY="$2"; shift 2 ;;
    --app-dir) APP_DIR="$2"; shift 2 ;;
    --identity) IDENTITY_FILE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "$HOST" || -z "$USER_NAME" || -z "$ENV_FILE" || -z "$CONFIG_FILE" || -z "$BUCKET" ]]; then
  usage
  exit 1
fi

if ! command -v aws >/dev/null 2>&1; then
  echo "aws CLI is required" >&2
  exit 1
fi

SSH_OPTS=()
if [[ -n "$IDENTITY_FILE" ]]; then
  SSH_OPTS+=(-i "$IDENTITY_FILE")
fi

REMOTE="${USER_NAME}@${HOST}"
RSYNC_RSH="ssh ${SSH_OPTS[*]}"

aws s3 cp "$CONFIG_FILE" "s3://${BUCKET}/${CONFIG_KEY}"

ssh "${SSH_OPTS[@]}" "$REMOTE" "mkdir -p '${APP_DIR}' '${APP_DIR}/local_files/vid-analyser'"

rsync -az --delete \
  --exclude ".git" \
  --exclude ".venv" \
  --exclude "__pycache__" \
  --exclude ".pytest_cache" \
  -e "$RSYNC_RSH" \
  ./ "$REMOTE:${APP_DIR}/"

scp "${SSH_OPTS[@]}" "$ENV_FILE" "$REMOTE:${APP_DIR}/.env"

ssh "${SSH_OPTS[@]}" "$REMOTE" "cd '${APP_DIR}' && docker compose up -d --build"
