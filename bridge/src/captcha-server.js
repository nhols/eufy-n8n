import http from 'http';
import { log } from './logger.js';

const CAPTCHA_PORT = Number(process.env.CAPTCHA_PORT ?? 8080);

/**
 * Tiny HTTP server that accepts captcha solutions.
 *
 * Usage:
 *   curl -X POST http://localhost:8080/captcha -d '{"captcha":"ABCD"}'
 *   # or simply:
 *   curl -X POST http://localhost:8080/captcha?code=ABCD
 *
 * The server holds a reference to the WS send function so it can forward
 * the captcha code to the eufy-security-ws bridge immediately.
 */
export class CaptchaServer {
  constructor(wsSend) {
    this.wsSend = wsSend;
    this.pendingCaptchaId = null;
    this.pendingCaptchaImage = null;
  }

  /** Called by the event handler when a captcha request event arrives. */
  onCaptchaRequest(captchaId, captchaImageBase64) {
    this.pendingCaptchaId = captchaId;
    this.pendingCaptchaImage = captchaImageBase64;
    log('🔐 ════════════════════════════════════════════');
    log('🔐  CAPTCHA REQUIRED');
    if (captchaId) log(`🔐  ID: ${captchaId}`);
    log(`🔐  Open http://localhost:${CAPTCHA_PORT}/captcha to view & solve`);
    log('🔐 ════════════════════════════════════════════');
  }

  /** Send a captcha solution through the existing WS connection. */
  solve(code) {
    log(`🔐 Sending captcha solution: ${code} (id=${this.pendingCaptchaId})`);
    this.wsSend('driver.set_captcha', {
      captchaId: this.pendingCaptchaId,
      captcha: code,
    });
    this.pendingCaptchaId = null;
    this.pendingCaptchaImage = null;
  }

  /** Render an HTML page that shows the captcha image and a submit form. */
  renderCaptchaPage() {
    if (!this.pendingCaptchaImage) {
      return `<!DOCTYPE html><html><body style="font-family:sans-serif;text-align:center;padding:4rem">
        <h1>No captcha pending</h1>
        <p>Waiting for Eufy to request one…</p>
        <script>setTimeout(()=>location.reload(), 5000)</script>
      </body></html>`;
    }

    // The captcha field from eufy-security-ws is a base64-encoded image.
    // It may or may not include the data-URI prefix.
    const src = this.pendingCaptchaImage.startsWith('data:')
      ? this.pendingCaptchaImage
      : `data:image/png;base64,${this.pendingCaptchaImage}`;

    return `<!DOCTYPE html><html><body style="font-family:sans-serif;text-align:center;padding:2rem">
      <h1>🔐 Captcha Required</h1>
      <p>ID: <code>${this.pendingCaptchaId ?? 'unknown'}</code></p>
      <img src="${src}" style="border:2px solid #333;margin:1rem auto;display:block;max-width:400px" />
      <form method="POST" action="/captcha" style="margin-top:1rem">
        <input name="code" type="text" placeholder="Enter captcha code"
               autofocus required
               style="font-size:1.5rem;padding:0.5rem;text-align:center;width:200px" />
        <br/><br/>
        <button type="submit" style="font-size:1.2rem;padding:0.5rem 2rem;cursor:pointer">Submit</button>
      </form>
      <script>
        document.querySelector('form').addEventListener('submit', async (e) => {
          e.preventDefault();
          const code = document.querySelector('input[name=code]').value;
          const res = await fetch('/captcha?code=' + encodeURIComponent(code), { method: 'POST' });
          const json = await res.json();
          document.body.innerHTML = json.ok
            ? '<h1 style="padding:4rem;color:green">✅ Submitted: ' + json.code + '</h1>'
            : '<h1 style="padding:4rem;color:red">❌ ' + (json.error || 'Failed') + '</h1>';
        });
      </script>
    </body></html>`;
  }

  /** Start the HTTP listener. */
  start() {
    const server = http.createServer((req, res) => {
      // Health check
      if (req.method === 'GET' && req.url === '/health') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ok', captchaPending: !!this.pendingCaptchaId }));
        return;
      }

      // Captcha page — renders the image and a form to submit the code
      if (req.method === 'GET' && req.url?.startsWith('/captcha')) {
        res.writeHead(200, { 'Content-Type': 'text/html' });
        res.end(this.renderCaptchaPage());
        return;
      }

      // Captcha submission
      if (req.method === 'POST' && req.url?.startsWith('/captcha')) {
        const url = new URL(req.url, `http://localhost:${CAPTCHA_PORT}`);
        const queryCode = url.searchParams.get('code');

        if (queryCode) {
          this.solve(queryCode);
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ ok: true, code: queryCode }));
          return;
        }

        // Read body (JSON or form-encoded)
        let body = '';
        req.on('data', (chunk) => (body += chunk));
        req.on('end', () => {
          try {
            let value;
            if (req.headers['content-type']?.includes('application/x-www-form-urlencoded')) {
              const params = new URLSearchParams(body);
              value = params.get('code') ?? params.get('captcha');
            } else {
              const parsed = JSON.parse(body);
              value = parsed.captcha ?? parsed.code;
            }
            if (!value) {
              res.writeHead(400, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({ error: 'Missing captcha/code field' }));
              return;
            }
            this.solve(value);
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ ok: true, code: value }));
          } catch {
            res.writeHead(400, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: 'Invalid JSON' }));
          }
        });
        return;
      }

      res.writeHead(404);
      res.end('Not found\n');
    });

    server.listen(CAPTCHA_PORT, () => {
      log(`🔐 Captcha server listening on :${CAPTCHA_PORT}`);
    });
  }
}
