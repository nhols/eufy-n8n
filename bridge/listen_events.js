import WebSocket from "ws";
import fs from "fs";
import path from "path";

const EUFY_WS_URL = process.env.EUFY_WS_URL ?? "ws://localhost:3000";
const API_SCHEMA = Number(process.env.API_SCHEMA ?? "21");
const DOORBELL_SN = process.env.DOORBELL_SN;
const HOMEBASE_SN = process.env.HOMEBASE_SN;
const IMAGE_DIR = process.env.IMAGE_DIR ?? "/app/local_files";
const IMAGE_PREFIX = process.env.IMAGE_PREFIX ?? "event-image";

let localQueryPending = false;
let localQuerySentAt = 0;
let localQueryQueued = false;

function log(...args) {
  console.log(`[${new Date().toISOString()}]`, ...args);
}

function logError(...args) {
  console.error(`[${new Date().toISOString()}]`, ...args);
}

function ensureDir(dirPath) {
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
  }
}

function normalizeBase64(value) {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if (trimmed.startsWith("data:image/")) {
    const parts = trimmed.split(",", 2);
    return parts.length === 2 ? parts[1] : null;
  }
  return trimmed.length > 0 ? trimmed : null;
}

function bufferFromUnknown(value) {
  if (!value) return null;
  if (typeof value === "string") {
    const b64 = normalizeBase64(value);
    return b64 ? Buffer.from(b64, "base64") : null;
  }
  const data =
    value?.data?.data ??
    value?.data ??
    (Array.isArray(value) ? value : null);

  if (!data || !Array.isArray(data)) return null;
  return Buffer.from(data);
}

function guessImageExtension(buffer) {
  if (!buffer || buffer.length < 4) return "jpg";
  if (buffer[0] === 0xff && buffer[1] === 0xd8) return "jpg";
  if (buffer[0] === 0x89 && buffer[1] === 0x50 && buffer[2] === 0x4e && buffer[3] === 0x47) return "png";
  if (buffer[0] === 0x47 && buffer[1] === 0x49 && buffer[2] === 0x46) return "gif";
  return "jpg";
}

function extractImageBufferFromEvent(event) {
  if (!event || typeof event !== "object") return null;
  const direct = bufferFromUnknown(event.image);
  if (direct) return direct;
  if (event.name === "picture") {
    const pic = bufferFromUnknown(event.value);
    if (pic) return pic;
  }
  const nested = event.data ?? event.event ?? event.result ?? null;
  if (nested) {
    const nestedImage = bufferFromUnknown(nested.image ?? nested.picture);
    if (nestedImage) return nestedImage;
    if (nested.name === "picture") {
      const nestedVal = bufferFromUnknown(nested.value);
      if (nestedVal) return nestedVal;
    }
  }
  return null;
}

function saveImageBuffer(buffer, serialNumber) {
  try {
    ensureDir(IMAGE_DIR);
    const ts = new Date().toISOString().replace(/[:.]/g, "-");
    const sn = serialNumber ?? "unknown";
    const ext = guessImageExtension(buffer);
    const fileName = `${IMAGE_PREFIX}-${sn}-${ts}.${ext}`;
    const filePath = path.join(IMAGE_DIR, fileName);
    fs.writeFileSync(filePath, buffer);
    log("Saved image:", filePath, `(${buffer.length} bytes)`);
  } catch (e) {
    logError("Failed to save image:", e.message);
  }
}

function redactEventForLog(event) {
  if (!event || typeof event !== "object") return event;
  const copy = { ...event };
  if (copy.image !== undefined) {
    copy.image = "<redacted>";
  }
  if (copy.name === "picture" && copy.value !== undefined) {
    copy.value = "<redacted>";
  }
  return copy;
}

let nextId = 1;
const pending = new Map(); // messageId -> { resolve, reject, timeout }

function send(ws, command, payload = {}) {
  const messageId = String(nextId++);
  const msg = { messageId, command, ...payload };
  ws.send(JSON.stringify(msg));
  return msg;
}

function request(ws, command, payload = {}, timeoutMs = 15000) {
  const messageId = String(nextId++);
  const msg = { messageId, command, ...payload };

  return new Promise((resolve, reject) => {
    const t = setTimeout(() => {
      pending.delete(messageId);
      reject(new Error(`Timeout waiting for ${command}`));
    }, timeoutMs);

    pending.set(messageId, { resolve, reject, timeout: t });
    ws.send(JSON.stringify(msg));
  });
}

const ws = new WebSocket(EUFY_WS_URL);

function sendDatabaseQueryLocal() {
  if (!HOMEBASE_SN || !DOORBELL_SN) {
    logError("HOMEBASE_SN/DOORBELL_SN not set; cannot run station.database_query_local.");
    return;
  }
  const formatYYYYMMDD = (d) => {
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1)}${pad(d.getUTCDate())}`;
  };

  const startDate = new Date(Date.now() - 1 * 24 * 60 * 60 * 1000);
  const endDate = new Date();

  const localPayload = {
    serialNumber: HOMEBASE_SN,
    serialNumbers: [DOORBELL_SN],
    startDate: formatYYYYMMDD(startDate),
    endDate: formatYYYYMMDD(endDate)
  };

  log("Query local payload (YYYYMMDD + device list):", JSON.stringify(localPayload));
  localQueryPending = true;
  localQuerySentAt = Date.now();
  request(ws, "station.database_query_local", localPayload, 60000)
    .then((localResp) => {
      log("Recent Video Events (Query Local - YYYYMMDD + device list):", JSON.stringify(localResp, null, 2));
      setTimeout(() => {
        if (localQueryPending) {
          const elapsed = Math.round((Date.now() - localQuerySentAt) / 1000);
          log(`No 'database query local' event received after ${elapsed}s.`);
        }
      }, 60000);
    })
    .catch((e) => {
      logError("station.database_query_local failed:", e.message);
    });
}

ws.on("open", async () => {
  log("Connected:", EUFY_WS_URL);

  // Init sequence: set schema + connect + listen.
  try {
    const schemaResp = await request(ws, "set_api_schema", { schemaVersion: API_SCHEMA });
    log(`Schema version set to ${API_SCHEMA}.`);

    send(ws, "start_listening");
    log("Listening for events...");

    log("Connecting driver...");
    // 10 minute timeout to allow for captcha entry
    const connectResp = await request(ws, "driver.connect", {}, 600000);
    log("Driver connected");

    if (HOMEBASE_SN) {
      try {
        const stationStatus = await request(ws, "station.is_connected", { serialNumber: HOMEBASE_SN }, 30000);
        log("Station connection status:", JSON.stringify(stationStatus, null, 2));
        if (stationStatus?.result?.connected === false) {
          log("Station not connected. Sending station.connect...");
          send(ws, "station.connect", { serialNumber: HOMEBASE_SN });
          localQueryQueued = true;
        }
        if (stationStatus?.result?.connected === true) {
          sendDatabaseQueryLocal();
        }
      } catch (e) {
        logError("Failed to check station connection status:", e.message);
      }
    }

    const targets = [
      { sn: DOORBELL_SN, type: "device" },
      { sn: HOMEBASE_SN, type: "station" }
    ];

    // Fetch commands in background so we don't block event listening (e.g. captcha)
    (async () => {
        log("Fetching recent video events...");
        try {
          if (!HOMEBASE_SN) {
            logError("HOMEBASE_SN is not set; skipping station queries.");
          } else {
                const latestPayload = { serialNumber: HOMEBASE_SN };
                log("Query latest info payload:", JSON.stringify(latestPayload));
                const videoEvents = await request(ws, "station.database_query_latest_info", latestPayload);
                log("Recent Video Events (Latest Info):", JSON.stringify(videoEvents, null, 2));

                const startMs = Date.now() - 7 * 24 * 60 * 60 * 1000;
                const endMs = Date.now();
                const driverEventPayload = { startTimestampMs: startMs, endTimestampMs: endMs, maxResults: 5 };

                log("Query driver.get_video_events payload:", JSON.stringify(driverEventPayload));
                const driverVideo = await request(ws, "driver.get_video_events", driverEventPayload, 60000);
                log("Driver Video Events:", JSON.stringify(driverVideo, null, 2));

                log("Query driver.get_alarm_events payload:", JSON.stringify(driverEventPayload));
                const driverAlarm = await request(ws, "driver.get_alarm_events", driverEventPayload, 60000);
                log("Driver Alarm Events:", JSON.stringify(driverAlarm, null, 2));

                log("Query driver.get_history_events payload:", JSON.stringify(driverEventPayload));
                const driverHistory = await request(ws, "driver.get_history_events", driverEventPayload, 60000);
                log("Driver History Events:", JSON.stringify(driverHistory, null, 2));

                const countStart = new Date(startMs);
                const countEnd = new Date(endMs);
                const countAttempts = [
                  {
                    label: "Date objects",
                    command: "station.database_count_by_date",
                    payload: { serialNumber: HOMEBASE_SN, startDate: countStart, endDate: countEnd }
                  },
                  {
                    label: "ISO strings",
                    command: "station.database_count_by_date",
                    payload: {
                      serialNumber: HOMEBASE_SN,
                      startDate: countStart.toISOString(),
                      endDate: countEnd.toISOString()
                    }
                  },
                  {
                    label: "ms timestamps",
                    command: "station.database_count_by_date",
                    payload: {
                      serialNumber: HOMEBASE_SN,
                      startDate: countStart.getTime(),
                      endDate: countEnd.getTime()
                    }
                  },
                  {
                    label: "camelCase command (as reported)",
                    command: "stationDatabaseCoundByDate",
                    payload: {
                      serialNumber: HOMEBASE_SN,
                      startDate: countStart.toISOString(),
                      endDate: countEnd.toISOString()
                    }
                  }
                ];

                for (const attempt of countAttempts) {
                  log(`Query station count payload (${attempt.label}):`, JSON.stringify(attempt.payload));
                  const countResp = await request(ws, attempt.command, attempt.payload, 60000);
                  log(`Station Database Count By Date (${attempt.label}):`, JSON.stringify(countResp, null, 2));
                  if (countResp?.success !== false) break;
                }

              if (!HOMEBASE_SN || !DOORBELL_SN) {
                logError("HOMEBASE_SN/DOORBELL_SN not set; skipping station.database_query_local.");
              } else if (!localQueryQueued) {
                // Only send immediately if we already confirmed station connected
                sendDatabaseQueryLocal();
              }
          }
        } catch (e) {
          logError("Failed to fetch video events:", e.message);
        }

        for (const { sn, type } of targets) {
            if (!sn) continue;
            log(`Fetching supported commands for ${sn} (${type})...`);
            try {
                // Give it a bit more time for initial commands
                const cmds = await request(ws, `${type}.get_commands`, { serialNumber: sn }, 60000);
                log(`Supported ${type.toUpperCase()} commands for ${sn}:`, JSON.stringify(cmds, null, 2));
            } catch (e) {
                logError(`Could not fetch ${type} commands for ${sn}:`, e.message);
            }
        }
    })();

  } catch (e) {
    logError("Failed during initialization sequence:", e);
    process.exit(1);
  }
});

ws.on("message", async (raw) => {
  let msg;
  try {
    msg = JSON.parse(raw.toString());
  } catch {
    return;
  }

  // Resolve command responses by messageId
  if (msg?.messageId && pending.has(String(msg.messageId))) {
    const p = pending.get(String(msg.messageId));
    clearTimeout(p.timeout);
    pending.delete(String(msg.messageId));
    p.resolve(msg);
    return;
  }

  if (msg.type === "event" && msg.event?.event === "captcha request") {
      log("=============== CAPTCHA REQUESTED ===============");
      log("Captcha ID:", msg.event.captchaId);
      log("Captcha Content:", msg.event.captcha); // Log content so user can see it (base64 or similar)
      log("To solve: make captcha code=<code_from_image>"); 
      log("=================================================");
      return;
  }

    if (msg.type === "event" && msg.event?.event === "database query local") {
      localQueryPending = false;
      log(`Database query local event received after ${Math.round((Date.now() - localQuerySentAt) / 1000)}s.`);
    }

      if (msg.type === "event" && msg.event?.event === "connected" && msg.event?.source === "station") {
        if (localQueryQueued) {
          localQueryQueued = false;
          log("Station connected; sending database_query_local now...");
          sendDatabaseQueryLocal();
        }
      }

    // Only log events
    if (msg.type === "event") {
      const serial = msg.event?.serialNumber;
      // If the event has a serial number, filter by our known devices
      if (serial) {
          const isTarget = (DOORBELL_SN && serial === DOORBELL_SN) || (HOMEBASE_SN && serial === HOMEBASE_SN);
          if (!isTarget) return;
      }
      const imageBuffer = extractImageBufferFromEvent(msg.event);
      if (imageBuffer) {
        saveImageBuffer(imageBuffer, serial);
      }
      const redactedEvent = redactEventForLog(msg.event);
      const safeMsg = { ...msg, event: redactedEvent };
      log("Event Received:", JSON.stringify(safeMsg, null, 2));
  }
});

ws.on("close", (code, reason) => {
  logError("WS closed:", code, reason?.toString());
  process.exit(1);
});

ws.on("error", (err) => {
  logError("WS error:", err);
  process.exit(1);
});
