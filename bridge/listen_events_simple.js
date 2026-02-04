import WebSocket from "ws";
import fs from "fs";
import path from "path";

const EUFY_WS_URL = process.env.EUFY_WS_URL ?? "ws://localhost:3000";
const API_SCHEMA = Number(process.env.API_SCHEMA ?? "21");
const DOORBELL_SN = process.env.DOORBELL_SN;
const HOMEBASE_SN = process.env.HOMEBASE_SN;
const IMAGE_DIR = process.env.IMAGE_DIR ?? "/app/local_files";
const IMAGE_PREFIX = process.env.IMAGE_PREFIX ?? "event-image";

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
const pending = new Map();

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

ws.on("open", async () => {
  log("Connected:", EUFY_WS_URL);

  try {
    await request(ws, "set_api_schema", { schemaVersion: API_SCHEMA });
    log(`Schema version set to ${API_SCHEMA}.`);

    ws.send(JSON.stringify({ messageId: String(nextId++), command: "start_listening" }));
    log("Listening for events...");

    log("Connecting driver...");
    // 10 minute timeout to allow for captcha entry
    await request(ws, "driver.connect", {}, 600000);
    log("Driver connected");
  } catch (e) {
    logError("Failed during initialization:", e);
    process.exit(1);
  }
});

ws.on("message", (raw) => {
  let msg;
  try {
    msg = JSON.parse(raw.toString());
  } catch {
    logError("Failed to parse message:", raw.toString());
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

  // Handle captcha requests
  if (msg.type === "event" && msg.event?.event === "captcha request") {
    log("=============== CAPTCHA REQUESTED ===============");
    log("Captcha ID:", msg.event.captchaId);
    log("Captcha Content:", msg.event.captcha);
    log("To solve: make captcha code=<code_from_image>");
    log("=================================================");
    return;
  }

  // Log all events
  if (msg.type === "event") {
    const serial = msg.event?.serialNumber;
    
    // Filter by serial number if present
    if (serial) {
      const isAllowed = (DOORBELL_SN && serial === DOORBELL_SN) || (HOMEBASE_SN && serial === HOMEBASE_SN);
      if (!isAllowed) {
        log("Ignoring event from serial number:", serial);
        return;
      }
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
