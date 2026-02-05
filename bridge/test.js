import WebSocket from "ws";
import fs from "fs";
import { execSync } from "child_process";
import axios from "axios";

const EUFY_WS_URL = process.env.EUFY_WS_URL ?? "ws://localhost:3000";
const HOMEBASE_SN = process.env.HOMEBASE_SN;
const DOORBELL_SN = process.env.DOORBELL_SN;
const N8N_WEBHOOK_URL = process.env.N8N_WEBHOOK_URL;

if (!HOMEBASE_SN) throw new Error("Missing HOMEBASE_SN");
if (!DOORBELL_SN) throw new Error("Missing DOORBELL_SN");
if (!N8N_WEBHOOK_URL) throw new Error("Missing N8N_WEBHOOK_URL");

const ws = new WebSocket(EUFY_WS_URL);
ws.on('error', e => console.log('Error:', e.message));
const send = (c, p) => { console.log('>>> ' + c); ws.send(JSON.stringify({ messageId: Date.now(), command: c, ...p })); };
const fmt = d => d.toISOString().slice(0,10).replace(/-/g,'');
const ts = () => new Date().toISOString();
const log = (...args) => console.log(`[${ts()}]`, ...args);

let videoChunks = [];
let outputPath = '/app/local_files/';
const sentEvents = new Set(); // Track events already sent to n8n
let connectTimeout = null;

const queryRecentVideos = () => {
    const t = new Date(), n = new Date(t); n.setDate(n.getDate()+1);
    log(`Querying station ${HOMEBASE_SN} for videos`);
    const queryParams = {
        serialNumber: HOMEBASE_SN, 
        serialNumbers: [], 
        startDate: fmt(t), 
        endDate: fmt(n), 
        eventType: 0, 
        detectionType: 0, 
        storageType: 0
    };
    log('📤 database_query_by_date params:', JSON.stringify(queryParams, null, 2));
    send('station.database_query_by_date', queryParams);
};

ws.on('open', () => {
    log('Connected!');
    send('set_api_schema', {schemaVersion:21});
    send('start_listening');
    send('driver.connect');
    
    // Set 10 minute timeout for driver.connect response
    connectTimeout = setTimeout(() => {
        log('⏱️  10 minute timeout reached, querying videos...');
        queryRecentVideos();
    }, 10 * 60 * 1000);
});

ws.on('message', async (d) => {
const m = JSON.parse(d);
const eventName = m.event?.event ?? (m.result?.state ? 'state' : '');
if (eventName !== 'download audio data' && eventName !== 'download video data') {
    // Only log if no serialNumber, or if serialNumber matches our devices
    if (!m.event?.serialNumber || m.event.serialNumber === DOORBELL_SN || m.event.serialNumber === HOMEBASE_SN) {
        log(m);
    }
}

// Handle driver.connect response
if (m.type === 'result' && m.success === true && connectTimeout) {
    log('✅ Driver connected, clearing timeout and querying videos...');
    clearTimeout(connectTimeout);
    connectTimeout = null;
    queryRecentVideos();
}

// Handle motion detected event
if (m.event?.event === 'motion detected' && 
    m.event?.serialNumber === DOORBELL_SN && 
    m.event?.state === false) {
    log('🚨 Motion detected event (state=false), querying videos...');
    queryRecentVideos();
}

if (m.event?.event === 'database query by date') {
    log('=== RESULTS ===');
    log('Events:', m.event.data?.length || 0);
    
    // Filter events by DOORBELL_SN
    const doorbellEvents = (m.event.data || []).filter(e => e.device_sn === DOORBELL_SN);
    log(`Doorbell events (${DOORBELL_SN}):`, doorbellEvents.length);
    
    if (doorbellEvents.length === 0) {
        log('No doorbell events found');
        return;
    }
    
    // Sort by start_time to get most recent event
    doorbellEvents.sort((a, b) => new Date(b.start_time) - new Date(a.start_time));
    const mostRecentEvent = doorbellEvents[0];
    
    log('Most recent event:', JSON.stringify(mostRecentEvent, null, 2));
    
    // Check if already sent to n8n
    if (sentEvents.has(mostRecentEvent.storage_path)) {
        log('Event already sent to n8n, skipping');
        return;
    }
    
    // Mark as sent and download
    sentEvents.add(mostRecentEvent.storage_path);
    outputPath = './local_files/' + mostRecentEvent.storage_path.split('/').pop().replace('.zxvideo', '.raw');
    log(`\nDownloading: ${mostRecentEvent.storage_path}`);
    
    const downloadParams = { serialNumber: mostRecentEvent.device_sn, path: mostRecentEvent.storage_path, cipherId: mostRecentEvent.cipher_id };
    log('📥 start_download params:', JSON.stringify(downloadParams, null, 2));
    
    send('device.start_download', downloadParams);
}

if (m.event?.event === 'download started') {
    log('Download started...');
    videoChunks = []; // Clear previous video chunks
}

if (m.event?.event === 'download video data' && m.event.buffer?.data) {
    videoChunks.push(Buffer.from(m.event.buffer.data));
    if (videoChunks.length % 100 === 0) process.stdout.write(`  ${videoChunks.length} chunks\r`);
}

if (m.event?.event === 'download finished') {
    const buffer = Buffer.concat(videoChunks);
    fs.writeFileSync(outputPath, buffer);
    const mp4Path = outputPath.replace('.raw', '.mp4');
    log(`\nSaved ${buffer.length} bytes to ${outputPath}`);
    
    // Run ffmpeg to convert to mp4
    try {
        const ffmpegCmd = `ffmpeg -y -f hevc -framerate 15 -i ${outputPath} -c copy -movflags +faststart ${mp4Path}`;
        log(`🎬 Running: ${ffmpegCmd}`);
        execSync(ffmpegCmd, { stdio: 'inherit' });
        log(`✅ Converted to ${mp4Path}`);
        
        // Send to n8n endpoint
        const mp4Data = fs.readFileSync(mp4Path);
        const mp4Base64 = mp4Data.toString('base64');
        
        const n8nResponse = await axios.post(
            N8N_WEBHOOK_URL,
            {
                receivedAt: new Date().toISOString(),
                stationSerialNumber: HOMEBASE_SN,
                data: {
                    mimeType: "video/mp4",
                    base64: mp4Base64,
                    filename: mp4Path.split('/').pop()
                }
            },
            { timeout: 30000 }
        );
        
        log('📨 Sent video to n8n');
        log('n8n response:', JSON.stringify({ status: n8nResponse.status, statusText: n8nResponse.statusText, data: n8nResponse.data }, null, 2));
    } catch (e) {
        log('❌ Failed to convert/send video:', e.message);
    }
}

if (m.success === false) { 
    console.log('ERROR:', m.error); 
}
});
