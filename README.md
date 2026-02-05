# eufy-n8n

Eufy doorbell → n8n automation bridge. Monitors a Eufy doorbell for motion/ring events, downloads recordings (video + audio) from the homebase, converts to MP4, and POSTs them to an n8n webhook.

## Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
│  Eufy Cloud  │◄────│    eufy-ws       │◄────│  eufy-bridge │──► n8n webhook
│  + Homebase  │     │  (WS server)     │     │  (Node.js)   │
└──────────────┘     └──────────────────┘     └──────┬───────┘
                       port 3000 (internal)          │ :8080
                                                     │ (captcha UI)
                     ┌──────────────────┐            │
                     │     Caddy        │            │
                     │  (reverse proxy) │      ┌─────┴───────┐
                     │  :80 / :443      │      │ local_files/│
                     └────────┬─────────┘      │ (mp4s, logs)│
                              │                └─────────────┘
                     ┌────────┴─────────┐
                     │       n8n        │
                     │  :5678           │
                     └──────────────────┘
```

### Services

| Service | Description |
|---|---|
| **eufy-ws** | [eufy-security-ws](https://github.com/bropat/eufy-security-ws) built from `develop` branches (both WS server and [eufy-security-client](https://github.com/bropat/eufy-security-client)). Exposes the Eufy API over WebSocket on port 3000 (internal only). |
| **eufy-bridge** | Node.js app that connects to eufy-ws, listens for doorbell events, downloads recordings with audio, converts to MP4 via ffmpeg, and POSTs to n8n. Also runs a captcha HTTP server on port 8080. |
| **n8n** | Workflow automation. Receives video webhooks from eufy-bridge. Exposed via Caddy at `https://{SUBDOMAIN}.{DOMAIN_NAME}`. |
| **caddy** | Reverse proxy with automatic HTTPS for n8n. |
| **log-exporter** | Exports Docker container logs to `local_files/logs/`. |

### Bridge internals

The bridge (`bridge/`) is split into modules:

| Module | Purpose |
|---|---|
| `index.js` | Entry point — wires everything together |
| `src/config.js` | Environment variables and constants |
| `src/ws-client.js` | WebSocket client with automatic reconnection and exponential backoff |
| `src/query-poller.js` | Polls `database_query_by_date` with exponential backoff (5s → 10s → 20s → 40s → 80s) until new recordings appear |
| `src/download-manager.js` | Serial download queue, collects video + audio chunks per device, muxes with ffmpeg, sends to n8n |
| `src/event-handlers.js` | Message dispatcher → named handler functions |
| `src/captcha-server.js` | HTTP server for captcha rendering and submission |

## Setup

### Prerequisites

- Docker and Docker Compose
- A domain pointed at your VM (for n8n HTTPS via Caddy)

### Environment

Copy `.env.example` (or create `.env`) with:

```env
EUFY_USERNAME=your-eufy-email@example.com
EUFY_PASSWORD=your-eufy-password
EUFY_COUNTRY=GB

DOORBELL_SN=T8213PXXXXXXXXXX
HOMEBASE_SN=T8030TXXXXXXXXXX

N8N_WEBHOOK_URL=https://your-domain.com/webhook/eufy

SUBDOMAIN=n8n
DOMAIN_NAME=your-domain.com
GENERIC_TIMEZONE=Europe/London
DATA_FOLDER=.
```

### Run

```sh
make start    # docker compose up -d
make logs     # tail eufy-bridge logs
make stop     # docker compose down
make rebuild  # rebuild & restart just the bridge
```

## Captcha handling

Eufy occasionally requires a captcha during login. When this happens:

1. The bridge logs a banner:
   ```
   🔐 ════════════════════════════════════════════
   🔐  CAPTCHA REQUIRED
   🔐  Open http://localhost:8080/captcha to view & solve
   🔐 ════════════════════════════════════════════
   ```

2. **Option A — Browser (recommended)**

   Open `http://localhost:8080/captcha` in your browser. The page renders the captcha image with a text input and submit button. If accessing remotely, use an SSH tunnel:
   ```sh
   ssh -L 8080:localhost:8080 your-vm
   ```
   Then open `http://localhost:8080/captcha` locally.

3. **Option B — Make target**
   ```sh
   make captcha code=ABCD
   ```

4. **Option C — curl**
   ```sh
   curl -X POST "http://localhost:8080/captcha?code=ABCD"
   ```

The `/health` endpoint returns whether a captcha is currently pending:
```sh
curl http://localhost:8080/health
# {"status":"ok","captchaPending":false}
```

## Cutting a release

This project runs from source via `docker compose build`. To deploy or update:

1. **Commit your changes:**
   ```sh
   git add -A && git commit -m "description of changes"
   ```

2. **Tag the release:**
   ```sh
   git tag v1.0.0
   git push origin master --tags
   ```

3. **On the VM — pull and rebuild:**
   ```sh
   cd /path/to/eufy-client
   git pull
   docker compose build      # rebuilds eufy-ws and eufy-bridge images
   docker compose up -d       # restarts with new images
   ```

   Or if only the bridge changed:
   ```sh
   git pull
   make rebuild
   ```

4. **To update the upstream eufy-security-ws / eufy-security-client** (e.g. to pick up new develop commits):
   ```sh
   docker compose build --no-cache eufy-ws
   docker compose up -d eufy-ws
   ```
   This re-clones both repos at their latest `develop` HEAD.

### What gets versioned

| What | Where | Versioning |
|---|---|---|
| Bridge code | `bridge/` | Git tags on this repo |
| eufy-security-ws | `eufy-ws/Dockerfile` | Pinned to `develop` branch; rebuild with `--no-cache` to update |
| n8n | `docker-compose.yml` | Uses `docker.n8n.io/n8nio/n8n` (latest); pin a tag for stability |
| Caddy | `docker-compose.yml` | Uses `caddy:latest`; pin a tag for stability |
