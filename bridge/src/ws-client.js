import WebSocket from 'ws';
import { EventEmitter } from 'events';
import { log } from './logger.js';

/**
 * WebSocket client with automatic reconnection and exponential backoff.
 *
 * Events emitted:
 *   'open'           – connection established (fires on every reconnect)
 *   'message' (obj)  – parsed JSON message from the server
 */
export class WsClient extends EventEmitter {
  constructor(url) {
    super();
    this.url = url;
    this.ws = null;
    this.reconnectDelay = 1_000;
    this.maxReconnectDelay = 60_000;
    this.connect();
  }

  connect() {
    log(`Connecting to ${this.url}…`);
    this.ws = new WebSocket(this.url);

    this.ws.on('open', () => {
      log('WebSocket connected');
      this.reconnectDelay = 1_000; // reset backoff on success
      this.emit('open');
    });

    this.ws.on('message', (raw) => {
      try {
        this.emit('message', JSON.parse(raw));
      } catch (e) {
        log('Failed to parse WS message:', e.message);
      }
    });

    this.ws.on('close', (code, reason) => {
      log(`WebSocket closed (code=${code}, reason=${reason})`);
      this.scheduleReconnect();
    });

    this.ws.on('error', (e) => {
      log('WebSocket error:', e.message);
    });
  }

  /** @private */
  scheduleReconnect() {
    log(`Reconnecting in ${this.reconnectDelay / 1000}s…`);
    setTimeout(() => this.connect(), this.reconnectDelay);
    this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
  }

  /** Send a command to the eufy-security-ws bridge. */
  send(command, params = {}) {
    log('>>>', command);
    this.ws.send(JSON.stringify({ messageId: Date.now().toString(), command, ...params }));
  }
}
