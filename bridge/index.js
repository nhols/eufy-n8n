import WebSocket from "ws";
import axios from "axios";

const EUFY_WS_URL = process.env.EUFY_WS_URL ?? "ws://localhost:3000";
const N8N_WEBHOOK_URL = process.env.N8N_WEBHOOK_URL;
const DOORBELL_SN = process.env.DOORBELL_SN; // strongly recommended
const API_SCHEMA = Number(process.env.API_SCHEMA ?? "21");

if (!N8N_WEBHOOK_URL) throw new Error("Missing N8N_WEBHOOK_URL");
if (!DOORBELL_SN) console.warn("⚠️ DOORBELL_SN not set; you may forward too many events.");

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

function extractSerial(evt) {
  return evt?.serialNumber ?? evt?.data?.serialNumber ?? evt?.device?.serialNumber;
}

function looksLikeDoorbellEvent(evt) {
  // This is intentionally “broad” because event shapes vary by schema/device.
  // We’ll still filter by DOORBELL_SN.
  const s = JSON.stringify(evt).toLowerCase();
  return (
    s.includes("doorbell") ||
    s.includes("ring") ||
    s.includes("motion") ||
    s.includes("person") ||
    s.includes("package") ||
    s.includes("push")
  );
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
      return resp;
    } catch (e) {
      lastErr = e;
    }
  }
  throw lastErr ?? new Error("Snapshot fetch failed");
}


const ws = new WebSocket(EUFY_WS_URL);

ws.on("open", () => {
  console.log("✅ Connected:", EUFY_WS_URL);

  // Init sequence: set schema + connect + listen.
  // Schema mismatches can cause schema_incompatible. :contentReference[oaicite:5]{index=5}
  send(ws, "set_api_schema", { schemaVersion: API_SCHEMA });
  send(ws, "driver.connect");
  send(ws, "start_listening");

  // Try to fetch driver history events
  (async () => {
    try {
      console.log("📜 Fetching driver history events...");
      const now = Date.now();
      const past = now - (7 * 24 * 60 * 60 * 1000); // 7 days ago

      const resp = await request(ws, "driver.get_history_events", {
        startTimestampMs: past,
        endTimestampMs: now,
        maxResults: 50
      });
      console.log("📜 History result:", JSON.stringify(resp, null, 2));
    } catch (err) {
      console.error("❌ Driver history query failed:", err.message);
    }
  })();
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

  // Otherwise treat as event
  if (msg.type === "result") return;
  
  const serial = extractSerial(msg);
  if (DOORBELL_SN && serial && serial !== DOORBELL_SN) return;
  if (!looksLikeDoorbellEvent(msg)) return;

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
        snapshot: {
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
