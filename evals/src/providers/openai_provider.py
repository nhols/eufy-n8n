"""OpenAI provider stub for future use."""

from __future__ import annotations

import base64
import json
import os
from typing import Any

from openai import AsyncOpenAI

from evals.src.providers.base import Provider
from evals.src.schemas import GenerateResult, ModelOutput, TokenUsage

USER_PROMPT = "Analyse this doorbell footage and produce the JSON output " "described in the system instruction."

RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "doorbell_analysis",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "ir_mode": {"type": "string", "enum": ["yes", "no", "unknown"]},
                "parking_spot_status": {
                    "type": "string",
                    "enum": [
                        "occupied",
                        "vacant",
                        "car entering",
                        "car leaving",
                        "unknown",
                    ],
                },
                "number_plate": {"type": ["string", "null"]},
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
            "additionalProperties": False,
        },
    },
}


class OpenAIProvider(Provider):
    """Calls the OpenAI API (for models that support video input)."""

    def __init__(self, model: str, generation_params: dict[str, Any] | None = None):
        super().__init__(model, generation_params)
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        self.client = AsyncOpenAI(api_key=api_key)

    async def generate(
        self,
        video_bytes: bytes,
        system_prompt: str,
        generation_params: dict[str, Any] | None = None,
    ) -> GenerateResult:
        params = {**self.generation_params, **(generation_params or {})}

        # Remove provider-specific params that don't apply to OpenAI
        params.pop("media_resolution", None)
        params.pop("fps", None)

        b64_video = base64.b64encode(video_bytes).decode("utf-8")

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "video_url",
                            "video_url": {"url": f"data:video/mp4;base64,{b64_video}"},
                        },
                        {"type": "text", "text": USER_PROMPT},
                    ],
                },
            ],
            response_format=RESPONSE_SCHEMA,
            **params,
        )

        raw = json.loads(response.choices[0].message.content)
        output = ModelOutput(**raw)

        # Extract token usage
        token_usage = TokenUsage()
        if response.usage:
            token_usage = TokenUsage(
                input_tokens=response.usage.prompt_tokens or 0,
                output_tokens=response.usage.completion_tokens or 0,
                total_tokens=response.usage.total_tokens or 0,
            )

        return GenerateResult(output=output, token_usage=token_usage)
