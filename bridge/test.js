import WebSocket from "ws";
import fs from "fs";

const EUFY_WS_URL = process.env.EUFY_WS_URL ?? "ws://localhost:3000";

const ws = new WebSocket(EUFY_WS_URL);
ws.on('error', e => console.log('Error:', e.message));
const send = (c, p) => { console.log('>>> ' + c); ws.send(JSON.stringify({ messageId: Date.now(), command: c, ...p })); };
const fmt = d => d.toISOString().slice(0,10).replace(/-/g,'');

let videoChunks = [];
let outputPath = '/app/local_files/';
let downloadComplete = false;

ws.on('open', () => {
console.log('Connected!');
send('set_api_schema', {schemaVersion:21});
send('start_listening');
});

ws.on('message', d => {
const m = JSON.parse(d);
console.log('<<< type:', m.type, 'event:', m.event?.event || m.result?.state ? 'state' : '');
console.log(m);

if (downloadComplete) return;

if (m.result?.state?.stations) {
    console.log('Stations:', m.result.state.stations);
    const t = new Date(), n = new Date(t); n.setDate(n.getDate()+1);
    m.result.state.stations.forEach(s => send('station.database_query_by_date', {
    serialNumber:s, serialNumbers:[], startDate:fmt(t), endDate:fmt(n), eventType:0, detectionType:0, storageType:0
    }));
}

if (m.event?.event === 'database query by date') {
    console.log('=== RESULTS ===');
    console.log('Events:', m.event.data?.length || 0);
    if (m.event.data?.[0]) {
        const r = m.event.data[0];
        console.log(JSON.stringify(r, null, 2));
        outputPath = './local_files/' + r.storage_path.split('/').pop().replace('.zxvideo', '.raw');
        console.log(`\nDownloading: ${r.storage_path}`);
        send('device.start_download', { serialNumber: r.device_sn, path: r.storage_path, cipherId: r.cipher_id });
    } else {
        ws.close(); process.exit();
    }
}

if (m.event?.event === 'download started') {
    console.log('Download started...');
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
    console.log(`\nSaved ${buffer.length} bytes to ${outputPath}`);
    console.log(`Convert to mp4: ffmpeg -f h264 -i ${outputPath} -c:v copy -movflags +faststart ${mp4Path}`);
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