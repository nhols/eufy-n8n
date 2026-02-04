import WebSocket from "ws";
import fs from "fs";
import path from "path";

const EUFY_WS_URL = process.env.EUFY_WS_URL ?? "ws://localhost:3000";
const HOMEBASE_SN = process.env.HOMEBASE_SN;
const IMAGE_DIR = process.env.IMAGE_DIR ?? "/app/local_files";

const latestImage = () => {
  const files = fs
    .readdirSync(IMAGE_DIR)
    .map((name) => path.join(IMAGE_DIR, name))
    .filter((p) => fs.statSync(p).isFile())
    .sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs);
  return files[0] ?? null;
};

const imagePath = latestImage();
const image = imagePath ? fs.readFileSync(imagePath).toString("base64") : null;

let nextId = 1;
const pending = new Map();
const request = (ws, command, payload = {}, timeoutMs = 60000) =>
  new Promise((resolve, reject) => {
    const messageId = String(nextId++);
    const msg = { messageId, command, ...payload };
    const t = setTimeout(() => {
      pending.delete(messageId);
      reject(new Error(`Timeout waiting for ${command}`));
    }, timeoutMs);
    pending.set(messageId, { resolve, timeout: t });
    ws.send(JSON.stringify(msg));
  });

const ws = new WebSocket(EUFY_WS_URL);

ws.on("open", async () => {
  if (!HOMEBASE_SN) throw new Error("HOMEBASE_SN is required.");
  await request(ws, "driver.connect", {}, 600000);

  const now = new Date();
  const start = new Date(now.getTime() - 24 * 60 * 60 * 1000);
  const yyyyMMdd = (d) =>
    `${d.getUTCFullYear()}${String(d.getUTCMonth() + 1).padStart(2, "0")}${String(d.getUTCDate()).padStart(2, "0")}`;

  const commands = [
    { name: "stationDatabaseQueryLatestInfo", payload: { serialNumber: HOMEBASE_SN, image } },
    {
      name: "stationDatabaseQueryLocal",
      payload: {
        serialNumber: HOMEBASE_SN,
        serialNumbers: [HOMEBASE_SN],
        startDate: yyyyMMdd(start),
        endDate: yyyyMMdd(now),
        image
      }
    },
    {
      name: "stationDatabaseQueryByDate",
      payload: { serialNumber: HOMEBASE_SN, startDate: start.toISOString(), endDate: now.toISOString(), image }
    },
    {
      name: "stationDatabaseCoundByDate",
      payload: { serialNumber: HOMEBASE_SN, startDate: start.toISOString(), endDate: now.toISOString(), image }
    }
  ];

  for (const cmd of commands) {
    const resp = await request(ws, cmd.name, cmd.payload, 60000);
    console.log(cmd.name, JSON.stringify(resp, null, 2));
  }

  ws.close();
});

ws.on("message", (raw) => {
  let msg;
  try {
    msg = JSON.parse(raw.toString());
  } catch {
    return;
  }
  if (msg?.messageId && pending.has(String(msg.messageId))) {
    const p = pending.get(String(msg.messageId));
    clearTimeout(p.timeout);
    pending.delete(String(msg.messageId));
    p.resolve(msg);
  }
});
