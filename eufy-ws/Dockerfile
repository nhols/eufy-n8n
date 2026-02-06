# Build eufy-security-ws from develop branches
# (both the WS server and the underlying client library)

FROM node:20-alpine AS build

RUN apk add --no-cache git python3 make g++

WORKDIR /build

# 1. Clone & build eufy-security-client from develop
RUN git clone --depth 1 -b develop https://github.com/bropat/eufy-security-client.git
WORKDIR /build/eufy-security-client
RUN npm ci && npm run build && npm pack

# 2. Clone & build eufy-security-ws from develop
WORKDIR /build
RUN git clone --depth 1 -b develop https://github.com/bropat/eufy-security-ws.git
WORKDIR /build/eufy-security-ws
RUN npm ci \
    && npm uninstall eufy-security-client \
    && npm i /build/eufy-security-client/eufy-security-client-*.tgz --force \
    && npm run build

# ── runtime ──────────────────────────────────────────────────────────

FROM node:20-alpine

RUN apk add --no-cache tini bash jq

WORKDIR /usr/src/app
COPY --from=build /build/eufy-security-ws /usr/src/app

EXPOSE 3000
VOLUME /data

ENTRYPOINT ["tini", "--"]
CMD ["/bin/bash", "/usr/src/app/docker/run.sh"]
