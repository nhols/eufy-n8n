import WebSocket from "ws";

const EUFY_WS_URL = process.env.EUFY_WS_URL ?? "ws://localhost:3000";
const API_SCHEMA = Number(process.env.API_SCHEMA ?? "21");
const DOORBELL_SN = process.env.DOORBELL_SN;
const HOMEBASE_SN = process.env.HOMEBASE_SN;

function log(...args) {
  console.log(`[${new Date().toISOString()}]`, ...args);
}

let nextId = 1;
const pending = new Map();

function request(ws, command, payload = {}, timeoutMs = 60000) {
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

function send(ws, command, payload = {}) {
  const messageId = String(nextId++);
  const msg = { messageId, command, ...payload };
  ws.send(JSON.stringify(msg));
}

const ws = new WebSocket(EUFY_WS_URL);

ws.on("open", async () => {
  log("Connected to", EUFY_WS_URL);

  try {
    // Set schema
    await request(ws, "set_api_schema", { schemaVersion: API_SCHEMA });
    log("Schema set");

    // Start listening
    send(ws, "start_listening");

    // Connect driver
    log("Connecting driver...");
    await request(ws, "driver.connect", {}, 600000);
    log("Driver connected");

    // Connect station
    log("Connecting station...");
    await request(ws, "station.connect", { serialNumber: HOMEBASE_SN }, 30000);
    log("Station connected");

    // Wait a bit for station to be ready
    await new Promise(resolve => setTimeout(resolve, 2000));

    // Define date range
    const startMs = Date.now() - 7 * 24 * 60 * 60 * 1000;
    const endMs = Date.now();
    const countStart = new Date(startMs);
    const countEnd = new Date(endMs);

    // Test 1: station.database_count_by_date
    log("\n=== TEST 1: station.database_count_by_date ===");
    const countPayload = {
      serialNumber: HOMEBASE_SN,
      startDate: countStart,
      endDate: countEnd
    };
    log("Payload:", JSON.stringify(countPayload));
    const countResp = await request(ws, "station.database_count_by_date", countPayload);
    log("Response:", JSON.stringify(countResp, null, 2));

    // Test 2: station.database_query_local
    log("\n=== TEST 2: station.database_query_local ===");
    const formatYYYYMMDD = (d) => {
      const pad = (n) => String(n).padStart(2, "0");
      return `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1)}${pad(d.getUTCDate())}`;
    };
    const localPayload = {
      serialNumber: HOMEBASE_SN,
      serialNumbers: [DOORBELL_SN],
      startDate: formatYYYYMMDD(countStart),
      endDate: formatYYYYMMDD(countEnd)
    };
    log("Payload:", JSON.stringify(localPayload));
    const localResp = await request(ws, "station.database_query_local", localPayload);
    log("Response:", JSON.stringify(localResp, null, 2));

    // Test 3: station.database_query_by_date
    log("\n=== TEST 3: station.database_query_by_date ===");
    const queryByDatePayload = {
      serialNumber: HOMEBASE_SN,
      startDate: countStart,
      endDate: countEnd
    };
    log("Payload:", JSON.stringify(queryByDatePayload));
    const queryByDateResp = await request(ws, "station.database_query_by_date", queryByDatePayload);
    log("Response:", JSON.stringify(queryByDateResp, null, 2));

    log("\n=== ALL TESTS COMPLETE ===");
    process.exit(0);

  } catch (e) {
    log("ERROR:", e.message);
    process.exit(1);
  }
});

ws.on("message", (raw) => {
  let msg;
  try {
    msg = JSON.parse(raw.toString());
  } catch {
    return;
  }

  // Resolve command responses
  if (msg?.messageId && pending.has(String(msg.messageId))) {
    const p = pending.get(String(msg.messageId));
    clearTimeout(p.timeout);
    pending.delete(String(msg.messageId));
    p.resolve(msg);
    return;
  }

  // Log events
  if (msg.type === "event") {
    log("Event:", msg.event?.event);
  }
});

ws.on("error", (err) => {
  log("WS error:", err);
  process.exit(1);
});

ws.on("close", () => {
  log("WS closed");
  process.exit(1);
});
