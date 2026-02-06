export const EUFY_WS_URL = process.env.EUFY_WS_URL ?? 'ws://localhost:3000';
export const HOMEBASE_SN = process.env.HOMEBASE_SN;
export const DOORBELL_SN = process.env.DOORBELL_SN;
export const N8N_WEBHOOK_URL = process.env.N8N_WEBHOOK_URL;
export const N8N_WEBHOOK_USER = process.env.N8N_WEBHOOK_USER;
export const N8N_WEBHOOK_PASSWORD = process.env.N8N_WEBHOOK_PASSWORD;
export const OUTPUT_DIR = process.env.OUTPUT_DIR ?? './local_files';

export const CONNECT_TIMEOUT_MS = 10 * 60 * 1000;       // 10 minutes
export const BACKOFF_DELAYS = [5000, 10000, 20000, 40000, 80000]; // ~2.5 min total
export const QUERY_RESPONSE_TIMEOUT_MS = 30_000;

if (!HOMEBASE_SN) throw new Error('Missing HOMEBASE_SN');
if (!DOORBELL_SN) throw new Error('Missing DOORBELL_SN');
if (!N8N_WEBHOOK_URL) throw new Error('Missing N8N_WEBHOOK_URL');
