#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  deploy.sh --host <host> --user <user> --env-file <path> [options]

Required:
  --host         Remote host or IP
  --user         SSH user
  --env-file     Local .env file to copy

Optional:
  --app-dir      Remote app dir (default: /opt/argusai)
  --identity     SSH identity file
EOF
}

HOST=""
USER_NAME=""
ENV_FILE=""
APP_DIR="/opt/argusai"
IDENTITY_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2 ;;
    --user) USER_NAME="$2"; shift 2 ;;
    --env-file) ENV_FILE="$2"; shift 2 ;;
    --app-dir) APP_DIR="$2"; shift 2 ;;
    --identity) IDENTITY_FILE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "$HOST" || -z "$USER_NAME" || -z "$ENV_FILE" ]]; then
  usage
  exit 1
fi

SSH_OPTS=()
if [[ -n "$IDENTITY_FILE" ]]; then
  SSH_OPTS+=(-i "$IDENTITY_FILE")
fi

REMOTE="${USER_NAME}@${HOST}"
RSYNC_RSH="ssh ${SSH_OPTS[*]}"

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
