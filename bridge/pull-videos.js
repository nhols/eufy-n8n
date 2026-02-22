#!/usr/bin/env node
/**
 * Pull videos from eufy-ws for a given date range.
 *
 * Reuses the existing bridge modules (WsClient, DownloadManager) but skips
 * the n8n webhook — just saves MP4s to the output directory.
 *
 * Usage:
 *   node bridge/pull-videos.js --start 20260204 --end 20260207
 *   node bridge/pull-videos.js --start 20260204 --end 20260207 --output evals/videos
 *
 * Environment variables (from .env):
 *   EUFY_WS_URL   — default ws://localhost:3000
 *   HOMEBASE_SN   — required
 *   DOORBELL_SN   — required
 */

import { WsClient } from './src/ws-client.js';
import { DownloadManager } from './src/download-manager.js';
import { log } from './src/logger.js';

// ── parse CLI args ───────────────────────────────────────────────────

function parseArgs() {
  const args = process.argv.slice(2);
  const opts = {
    start: null,
    end: null,
    output: process.env.OUTPUT_DIR ?? './local_files',
    wsUrl: process.env.EUFY_WS_URL ?? 'ws://localhost:3000',
    homebaseSn: process.env.HOMEBASE_SN,
    doorbellSn: process.env.DOORBELL_SN,
  };

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case '--start': case '-s': opts.start = args[++i]; break;
      case '--end':   case '-e': opts.end = args[++i]; break;
      case '--output': case '-o': opts.output = args[++i]; break;
      case '--ws-url': opts.wsUrl = args[++i]; break;
      case '--homebase-sn': opts.homebaseSn = args[++i]; break;
      case '--doorbell-sn': opts.doorbellSn = args[++i]; break;
      case '--help': case '-h':
        console.log(`Usage: node bridge/pull-videos.js --start YYYYMMDD --end YYYYMMDD [options]

Options:
  --start, -s     Start date (YYYYMMDD, inclusive)         [required]
  --end, -e       End date (YYYYMMDD, exclusive)           [required]
  --output, -o    Output directory                         [default: ./local_files]
  --ws-url        eufy-ws WebSocket URL                    [default: ws://localhost:3000]
  --homebase-sn   HomeBase serial number                   [env: HOMEBASE_SN]
  --doorbell-sn   Doorbell serial number                   [env: DOORBELL_SN]`);
        process.exit(0);
    }
  }

  if (!opts.start || !opts.end) {
    console.error('❌ --start and --end are required. Use --help for usage.');
    process.exit(1);
  }
  if (!opts.homebaseSn) {
    console.error('❌ HOMEBASE_SN env var or --homebase-sn is required.');
    process.exit(1);
  }
  if (!opts.doorbellSn) {
    console.error('❌ DOORBELL_SN env var or --doorbell-sn is required.');
    process.exit(1);
  }

  return opts;
}

const opts = parseArgs();

// ── subclass DownloadManager to skip n8n POST ────────────────────────

/** How long to wait for a single download before skipping it. */
const DOWNLOAD_TIMEOUT_MS = 10_000; // 10 seconds

class PullDownloadManager extends DownloadManager {
  constructor(wsSend) {
    super(wsSend);
    this._downloadTimer = null;
  }

  /** Start a timeout whenever a new download begins processing. */
  processQueue() {
    if (this.isDownloading || this.queue.length === 0) return;

    const evt = this.queue.shift();
    this.isDownloading = true;

    const basename = evt.storage_path.split('/').pop().replace('.zxvideo', '');
    this.currentDownload = {
      serialNumber: evt.device_sn,
      storagePath: evt.storage_path,
      cipherId: evt.cipher_id,
      outputBasename: basename,
      startTime: evt.start_time,
      endTime: evt.end_time,
    };

    this.activeDownloads.set(evt.device_sn, {
      videoChunks: [],
      audioChunks: [],
      metadata: null,
    });

    log(`📥 start_download: ${evt.storage_path}`);
    this.wsSend('device.start_download', {
      serialNumber: evt.device_sn,
      path: evt.storage_path,
      cipherId: evt.cipher_id,
    });

    // Per-download timeout — skip if stuck
    clearTimeout(this._downloadTimer);
    this._downloadTimer = setTimeout(() => {
      log(`⏱️  Download timed out after ${DOWNLOAD_TIMEOUT_MS / 1000}s: ${evt.storage_path}`);
      this.activeDownloads.delete(evt.device_sn);
      this.isDownloading = false;
      this.currentDownload = null;
      this.completedCount++;
      this.logOverallProgress();
      this.processQueue();
    }, DOWNLOAD_TIMEOUT_MS);
  }

  /**
   * Override sendToN8n to be a no-op — we just want the MP4 on disk.
   * Also override onDownloadFinished to skip the mp4 deletion.
   */
  async onDownloadFinished(serialNumber) {
    clearTimeout(this._downloadTimer);
    const dl = this.activeDownloads.get(serialNumber);
    if (!dl) {
      log(`⚠️  download finished for unknown device ${serialNumber}`);
      this.isDownloading = false;
      this.processQueue();
      return;
    }

    const basename = this.currentDownload?.outputBasename ?? serialNumber;
    this.activeDownloads.delete(serialNumber);

    const fs = await import('fs');
    const path = await import('path');

    fs.mkdirSync(this.outputDir, { recursive: true });

    const videoRawPath = path.join(this.outputDir, `${basename}.video.raw`);
    const audioRawPath = path.join(this.outputDir, `${basename}.audio.raw`);
    const mp4Path = path.join(this.outputDir, `${basename}.mp4`);

    // Skip if MP4 already exists
    if (fs.existsSync(mp4Path)) {
      log(`⏭️  ${mp4Path} already exists, skipping`);
      this.isDownloading = false;
      this.currentDownload = null;
      this.completedCount++;
      this.logOverallProgress();
      this.processQueue();
      return;
    }

    try {
      const { execSync } = await import('child_process');

      // Write raw streams
      const videoBuffer = Buffer.concat(dl.videoChunks);
      fs.writeFileSync(videoRawPath, videoBuffer);

      const hasAudio = dl.audioChunks.length > 0;
      if (hasAudio) {
        const audioBuffer = Buffer.concat(dl.audioChunks);
        fs.writeFileSync(audioRawPath, audioBuffer);
      }

      // ffmpeg mux
      const videoCodec = dl.metadata?.videoCodec ?? 'hevc';
      const videoFPS = dl.metadata?.videoFPS ?? 15;
      const videoFmt = videoCodec === 'h264' ? 'h264' : 'hevc';

      let ffmpegCmd;
      if (hasAudio) {
        ffmpegCmd = [
          'ffmpeg -y',
          `-f ${videoFmt} -framerate ${videoFPS} -i ${videoRawPath}`,
          `-f aac -i ${audioRawPath}`,
          '-c:v copy -c:a copy -movflags +faststart',
          mp4Path,
        ].join(' ');
      } else {
        ffmpegCmd = [
          'ffmpeg -y',
          `-f ${videoFmt} -framerate ${videoFPS} -i ${videoRawPath}`,
          '-c copy -movflags +faststart',
          mp4Path,
        ].join(' ');
      }

      execSync(ffmpegCmd, { stdio: 'pipe' });
      const sizeMB = (fs.statSync(mp4Path).size / (1024 * 1024)).toFixed(1);
      log(`✅ ${mp4Path} (${sizeMB}MB)`);

      // Clean up raw files only (keep MP4)
      try { fs.unlinkSync(videoRawPath); } catch { /* ignore */ }
      if (hasAudio) try { fs.unlinkSync(audioRawPath); } catch { /* ignore */ }
    } catch (e) {
      log(`❌ Failed to convert ${basename}:`, e.message);
    } finally {
      this.isDownloading = false;
      this.currentDownload = null;
      this.completedCount++;
      this.logOverallProgress();
      this.processQueue();
    }
  }

  /** No-op — we don't send to n8n. */
  async sendToN8n() {}
}

// ── main ─────────────────────────────────────────────────────────────

log(`Connecting to ${opts.wsUrl}...`);
log(`Date range: ${opts.start} → ${opts.end}`);
log(`Output: ${opts.output}`);
log(`HomeBase: ${opts.homebaseSn}, Doorbell: ${opts.doorbellSn}`);

const ws = new WsClient(opts.wsUrl);
const send = (cmd, params) => ws.send(cmd, params);

const downloadManager = new PullDownloadManager(send);
downloadManager.outputDir = opts.output;
downloadManager.completedCount = 0;
downloadManager.totalCount = 0;
downloadManager.logOverallProgress = function () {
  log(`📊 Progress: ${this.completedCount}/${this.totalCount} videos`);
  if (this.completedCount >= this.totalCount && this.totalCount > 0) {
    log(`\n✅ Done! Downloaded ${this.completedCount} video(s) to ${this.outputDir}/`);
    process.exit(0);
  }
};

let queryResolved = false;

ws.on('open', () => {
  log('Connected — setting up...');
  ws.send('set_api_schema', { schemaVersion: 21 });
  ws.send('start_listening');
  ws.send('driver.connect');

  // Safety timeout — fire query even if driver.connect doesn't confirm
  setTimeout(() => {
    if (!queryResolved) {
      log('⏱️  Timeout waiting for driver.connect, firing query anyway...');
      fireQuery();
    }
  }, 30_000);
});

ws.on('message', (msg) => {
  const eventName = msg.event?.event ?? '';

  // driver.connect success → fire query
  if (msg.type === 'result' && msg.success === true && !queryResolved) {
    log('✅ Driver connected');
    fireQuery();
    return;
  }

  // Database query results
  if (eventName === 'database query by date') {
    const data = msg.event?.data ?? [];
    const doorbellEvents = data.filter((e) => e.device_sn === opts.doorbellSn);

    log(`Found ${doorbellEvents.length} event(s) for ${opts.doorbellSn} (${data.length} total)`);

    if (doorbellEvents.length === 0) {
      log('No events found in date range. Exiting.');
      process.exit(0);
    }

    // Sort chronologically
    doorbellEvents.sort((a, b) => new Date(a.start_time) - new Date(b.start_time));
    downloadManager.totalCount = doorbellEvents.length;
    downloadManager.enqueue(doorbellEvents);
    return;
  }

  // Download lifecycle — forward to DownloadManager
  if (eventName === 'download started') {
    downloadManager.onDownloadStarted(msg.event?.serialNumber, msg.event?.metadata ?? {});
  }
  if (eventName === 'download video data' && msg.event?.buffer?.data) {
    downloadManager.onVideoData(msg.event.serialNumber, msg.event.buffer.data);
  }
  if (eventName === 'download audio data' && msg.event?.buffer?.data) {
    downloadManager.onAudioData(msg.event.serialNumber, msg.event.buffer.data);
  }
  if (eventName === 'download finished') {
    downloadManager.onDownloadFinished(msg.event?.serialNumber);
  }
});

function fireQuery() {
  if (queryResolved) return;
  queryResolved = true;

  log(`Querying events: ${opts.start} → ${opts.end}`);
  send('station.database_query_by_date', {
    serialNumber: opts.homebaseSn,
    serialNumbers: [],
    startDate: opts.start,
    endDate: opts.end,
    eventType: 0,
    detectionType: 0,
    storageType: 0,
  });
}
