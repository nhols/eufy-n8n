import WebSocket from "ws";
import axios from "axios";

const EUFY_WS_URL = process.env.EUFY_WS_URL ?? "ws://localhost:3000";
const N8N_WEBHOOK_URL = process.env.N8N_WEBHOOK_URL;
const DOORBELL_SN = process.env.DOORBELL_SN; // strongly recommended
const HOMEBASE_SN = process.env.HOMEBASE_SN;
const API_SCHEMA = Number(process.env.API_SCHEMA ?? "21");
const THROTTLE_SECONDS = Number(process.env.THROTTLE_SECONDS ?? "10");

if (!N8N_WEBHOOK_URL) throw new Error("Missing N8N_WEBHOOK_URL");
if (!DOORBELL_SN) console.warn("⚠️ DOORBELL_SN not set; you may forward too many events.");
if (!HOMEBASE_SN) console.warn("⚠️ HOMEBASE_SN not set; some station events may be ignored.");

let nextId = 1;
const pending = new Map(); // messageId -> { resolve, reject, timeout }
const lastSent = new Map(); // serial -> timestamp

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

function extractSerial(evt) {
  return evt?.serialNumber ?? evt?.event?.serialNumber ?? evt?.data?.serialNumber ?? evt?.device?.serialNumber;
}



function bufferFromEufyPicture(pic) {
  // Common shapes seen:
  // - { data: { type: "Buffer", data: [255,216,...] } }
  // - { type: "Buffer", data: [...] }
  // - raw array of numbers
  const data =
    pic?.data?.data ??
    pic?.data ??
    (Array.isArray(pic) ? pic : null);

  if (!data || !Array.isArray(data)) return null;
  return Buffer.from(data);
}

async function fetchSnapshot(ws, serialNumber) {
  // Correct command name is snake_case: device.get_properties
  const attempts = [
    { command: "device.get_properties", payload: { serialNumber } },
    { command: "device.get_properties", payload: { serialNumber, properties: ["picture"] } },
  ];

  let lastErr;
  for (const a of attempts) {
    try {
      const resp = await request(ws, a.command, a.payload);
      const safeLog = JSON.stringify(resp, (k, v) => (k === "picture" ? "<redacted_buffer>" : v), 2);
      console.log(`✅ Snapshot fetch succeeded for command ${a.command}:`, safeLog);
      return resp;
    } catch (e) {
      console.warn(`⚠️ Snapshot fetch attempt failed for command ${a.command}:`, e);
      lastErr = e;
    }
  }
  throw lastErr ?? new Error("Snapshot fetch failed");
}


const ws = new WebSocket(EUFY_WS_URL);

ws.on("open", async () => {
  console.log("✅ Connected:", EUFY_WS_URL);

  // Init sequence: set schema + connect + listen.
  try {
    const schemaResp = await request(ws, "set_api_schema", { schemaVersion: API_SCHEMA });
    console.log(`✅ Schema version set to ${API_SCHEMA}. Server response:`, JSON.stringify(schemaResp));

    console.log("🔌 Connecting driver...");
    const connectResp = await request(ws, "driver.connect");
    console.log("✅ Driver connection response:", JSON.stringify(connectResp));

    send(ws, "start_listening");

    const targets = [
        { sn: DOORBELL_SN, type: "device" },
        { sn: HOMEBASE_SN, type: "station" }
    ];

    for (const { sn, type } of targets) {
        if (!sn) continue;
        console.log(`🔍 Fetching supported commands for ${sn} (${type})...`);
        
        try {
            const cmds = await request(ws, `${type}.get_commands`, { serialNumber: sn });
            console.log(`📜 Supported ${type.toUpperCase()} commands for ${sn}:`, JSON.stringify(cmds, null, 2));
        } catch (e) {
             console.warn(`⚠️ Could not fetch ${type} commands for ${sn}:`, e.message);
        }
    }
  } catch (e) {
    console.error("❌ Failed during initialization sequence:", e);
  }
});

ws.on("message", async (raw) => {
  let msg;
  try {
    msg = JSON.parse(raw.toString());
    if (msg.type === "result") return;
    console.log("📨 Received message:", JSON.stringify(msg, null, 2));
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
      console.log("=============== CAPTCHA REQUESTED ===============");
      console.log("Captcha ID:", msg.event.captchaId);
      console.log("Captcha Content:");
      console.log(msg.event.captcha);
      console.log("=================================================");
      return;
  }
  
  const serial = extractSerial(msg);

  // Filter out events that don't match our target doorbell
  if (DOORBELL_SN && serial && serial !== DOORBELL_SN) {
      console.log(`Ignoring event for ${serial} (expected ${DOORBELL_SN})`);
      return;
  }

  const now = Date.now();
  const throttleKey = serial || "unknown";
  const lastTime = lastSent.get(throttleKey) || 0;
  const throttleMs = THROTTLE_SECONDS * 1000;

  if (now - lastTime < throttleMs) {
    console.log(`⏳ Throttling event for ${throttleKey} (too soon)`);
    return;
  }

  lastSent.set(throttleKey, now);
  console.log(JSON.stringify(msg, null, 2));
  console.log("📸 Fetching snapshot for sensitive event:", msg.command || "unknown", "serial:", serial);
  try {
    const propsResp = await fetchSnapshot(ws, DOORBELL_SN ?? serial);

    // Try to locate `picture` in the response
    const props =
      propsResp?.result?.properties ??
      propsResp?.result ??
      propsResp?.data ??
      propsResp;

    const pic = props?.picture ?? props?.properties?.picture;
    const buf = bufferFromEufyPicture(pic);

    if (propsResp?.success === false) {
        console.warn("❌ get_properties failed:", propsResp?.errorCode, propsResp);
        return;
    }

    if (!buf) {
        console.warn("⚠️ No picture data found in response properties, cannot send snapshot.");
        return;
    }

    const snapshotBase64 = buf.toString("base64");

    await axios.post(
      N8N_WEBHOOK_URL,
      {
        receivedAt: new Date().toISOString(),
        doorbellSerialNumber: DOORBELL_SN ?? serial,
        eufyEvent: msg,
        data: {
          mimeType: "image/jpeg",
          base64: snapshotBase64
        }
      },
      { timeout: 15000 }
    );

    console.log("📨 Sent event + snapshot to n8n");
  } catch (e) {
    console.error("❌ Failed to fetch/send snapshot:", e);
  }
});

ws.on("close", (code, reason) => {
  console.error("WS closed:", code, reason?.toString());
  process.exit(1);
});

ws.on("error", (err) => {
  console.error("WS error:", err);
  process.exit(1);
});

