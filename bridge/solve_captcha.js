import WebSocket from "ws";

const EUFY_WS_URL = process.env.EUFY_WS_URL ?? "ws://eufy-ws:3000";
const CAPTCHA = process.env.CAPTCHA;

if (!CAPTCHA) {
    console.error("Please set CAPTCHA environment variable. Usage: CAPTCHA=1234 node solve_captcha.js");
    process.exit(1);
}

const ws = new WebSocket(EUFY_WS_URL);

ws.on("open", () => {
    console.log("Connected to", EUFY_WS_URL);
    // schema version match might be needed?
    // The server expects set_api_schema first usually? 
    // But driver.set_captcha might work directly.
    
    // We'll just send the captcha command.
    const msg = {
        messageId: "captcha-sol-1",
        command: "driver.set_captcha",
        captcha: CAPTCHA
    };
    ws.send(JSON.stringify(msg));
    console.log("Sent captcha code:", CAPTCHA);
});

ws.on("message", (data) => {
    try {
        const msg = JSON.parse(data.toString());
        // ignore other events
        if (msg.messageId === "captcha-sol-1") {
            console.log("Response:", JSON.stringify(msg, null, 2));
            if (msg.result?.result === true || msg.result === true) {
                 console.log("✅ Captcha accepted!");
            } else {
                 console.log("❌ Captcha rejected or failed.");
            }
            ws.close();
        }
    } catch(e) {
        // ignore
    }
});

ws.on("error", (e) => {
    console.error("WS Error:", e);
    process.exit(1);
});
