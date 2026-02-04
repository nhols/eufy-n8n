import WebSocket from "ws";
import fs from "fs";
import { execSync } from "child_process";
import axios from "axios";

const EUFY_WS_URL = process.env.EUFY_WS_URL ?? "ws://localhost:3000";
const HOMEBASE_SN = process.env.HOMEBASE_SN;
const N8N_WEBHOOK_URL = process.env.N8N_WEBHOOK_URL;

if (!HOMEBASE_SN) throw new Error("Missing HOMEBASE_SN");
if (!N8N_WEBHOOK_URL) throw new Error("Missing N8N_WEBHOOK_URL");

const ws = new WebSocket(EUFY_WS_URL);
ws.on('error', e => console.log('Error:', e.message));
const send = (c, p) => { console.log('>>> ' + c); ws.send(JSON.stringify({ messageId: Date.now(), command: c, ...p })); };
const fmt = d => d.toISOString().slice(0,10).replace(/-/g,'');
const ts = () => new Date().toISOString();
const log = (...args) => console.log(`[${ts()}]`, ...args);

let videoChunks = [];
let outputPath = '/app/local_files/';
let downloadComplete = false;
const downloadedVideos = new Set(); // Track already downloaded videos

ws.on('open', () => {
log('Connected!');
send('set_api_schema', {schemaVersion:21});
send('start_listening');
});

ws.on('message', async (d) => {
const m = JSON.parse(d);
log('<<< type:', m.type, 'event:', m.event?.event ?? (m.result?.state ? 'state' : ''));

if (downloadComplete) return;

if (m.result?.state?.stations) {
    log('Stations:', m.result.state.stations);
    // Only query the specified HOMEBASE_SN station
    if (m.result.state.stations.includes(HOMEBASE_SN)) {
        const t = new Date(), n = new Date(t); n.setDate(n.getDate()+1);
        log(`Querying station ${HOMEBASE_SN} for videos`);
        send('station.database_query_by_date', {
            serialNumber: HOMEBASE_SN, 
            serialNumbers: [], 
            startDate: fmt(t), 
            endDate: fmt(n), 
            eventType: 0, 
            detectionType: 0, 
            storageType: 0
        });
    } else {
        console.warn(`⚠️ Station ${HOMEBASE_SN} not found in state`);
        ws.close(); 
        process.exit(1);
    }
}

if (m.event?.event === 'database query by date') {
    log('=== RESULTS ===');
    log('Events:', m.event.data?.length || 0);
    
    // Find first video not yet downloaded
    const undownloadedVideo = m.event.data?.find(r => !downloadedVideos.has(r.storage_path));
    
    if (undownloadedVideo) {
        const r = undownloadedVideo;
        log(JSON.stringify(r, null, 2));
        outputPath = './local_files/' + r.storage_path.split('/').pop().replace('.zxvideo', '.raw');
        log(`\nDownloading: ${r.storage_path}`);
        
        const downloadParams = { serialNumber: r.device_sn, path: r.storage_path, cipherId: r.cipher_id };
        log('📥 start_download params:', JSON.stringify(downloadParams, null, 2));
        
        downloadedVideos.add(r.storage_path);
        send('device.start_download', downloadParams);
    } else {
        log('No new videos to download');
        ws.close(); 
        process.exit();
    }
}

if (m.event?.event === 'download started') {
    log('Download started...');
}

if (m.event?.event === 'download video data' && m.event.buffer?.data) {
    videoChunks.push(Buffer.from(m.event.buffer.data));
    if (videoChunks.length % 100 === 0) process.stdout.write(`  ${videoChunks.length} chunks\r`);
}

if (m.event?.event === 'download finished') {
    downloadComplete = true;
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
    
    ws.close();
    process.exit(0);
}

if (m.success === false) { 
    console.log('ERROR:', m.error); 
    ws.close(); 
    process.exit(1); 
}
});

setTimeout(() => { console.log('Timeout'); process.exit(1); }, 120000);