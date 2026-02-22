import json

with open("sys_prompt.md", "r") as f:
    SYS_PROMPT = f.read()

data = {
    "contents": [
        {
            "role": "user",
            "parts": [
                {
                    "inlineData": {"mimeType": "video/mp4", "data": "{{ $('Webhook').item.json.body.data.base64 }}"},
                    "videoMetadata": {"fps": 2},
                },
                {
                    "text": "Analyse this doorbell footage and produce the JSON output described in the system instruction."
                },
            ],
        }
    ],
    "generationConfig": {
        "mediaResolution": "MEDIA_RESOLUTION_HIGH",
        "responseMimeType": "application/json",
        "responseSchema": {
            "type": "object",
            "properties": {
                "ir_mode": {"type": "string", "enum": ["yes", "no", "unknown"]},
                "parking_spot_status": {
                    "type": "string",
                    "enum": ["occupied", "vacant", "car entering", "car leaving", "unknown"],
                },
                "number_plate": {
                    "type": "string",
                    "description": "Set as null if unreadable or not applicable",
                    "nullable": True,
                },
                "events_description": {"type": "string"},
                "summary": {"type": "string"},
                "send_notification": {"type": "boolean"},
            },
            "required": [
                "ir_mode",
                "parking_spot_status",
                "number_plate",
                "events_description",
                "summary",
                "send_notification",
            ],
            "propertyOrdering": [
                "ir_mode",
                "parking_spot_status",
                "number_plate",
                "events_description",
                "summary",
                "send_notification",
            ],
        },
    },
    "systemInstruction": {"parts": [{"text": SYS_PROMPT}]},
}

print(json.dumps(data, indent=2))
