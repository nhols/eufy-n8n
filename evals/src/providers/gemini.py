"""Gemini provider using the google-genai SDK."""

from __future__ import annotations

import json
import os
from typing import Any

from google import genai
from google.genai import types

from evals.src.providers.base import Provider
from evals.src.schemas import GenerateResult, ModelOutput, TokenUsage

# The Gemini response schema matching build_gemini_json.py
RESPONSE_SCHEMA: dict[str, Any] = {
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
}

USER_PROMPT = "Analyse this doorbell footage and produce the JSON output " "described in the system instruction."


class GeminiProvider(Provider):
    """Calls the Gemini API via the google-genai SDK."""

    def __init__(self, model: str, generation_params: dict[str, Any] | None = None):
        super().__init__(model, generation_params)
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        self.client = genai.Client(api_key=api_key)

    async def generate(
        self,
        video_bytes: bytes,
        system_prompt: str,
        generation_params: dict[str, Any] | None = None,
    ) -> GenerateResult:
        params = {**self.generation_params, **(generation_params or {})}

        # Build generation config
        media_resolution = params.pop("media_resolution", None)
        fps = params.pop("fps", 2)

        config_kwargs: dict[str, Any] = dict(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=RESPONSE_SCHEMA,
            **params,
        )
        if media_resolution is not None:
            config_kwargs["media_resolution"] = media_resolution

        config = types.GenerateContentConfig(**config_kwargs)

        # Build content parts: video + text prompt (inline pattern per docs)
        video_part = types.Part(
            inline_data=types.Blob(data=video_bytes, mime_type="video/mp4"),
            video_metadata=types.VideoMetadata(fps=fps),
        )
        text_part = types.Part(text=USER_PROMPT)

        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=types.Content(
                parts=[video_part, text_part],
            ),
            config=config,
        )

        # Parse the JSON response
        raw = json.loads(response.text)
        output = ModelOutput(**raw)

        # Extract token usage
        token_usage = TokenUsage()
        if response.usage_metadata:
            token_usage = TokenUsage(
                input_tokens=response.usage_metadata.prompt_token_count or 0,
                output_tokens=response.usage_metadata.candidates_token_count or 0,
                total_tokens=response.usage_metadata.total_token_count or 0,
            )

        return GenerateResult(output=output, token_usage=token_usage)
