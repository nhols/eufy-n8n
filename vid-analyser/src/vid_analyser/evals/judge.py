from typing import Protocol

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel

from vid_analyser.evals.config import JudgeConfig
from vid_analyser.evals.report_model import JudgeResult


class _JudgeSchema(BaseModel):
    covered_items: list[str]
    contradicted_items: list[str]
    rationale: str


class GeminiEventJudge:
    def __init__(self, model: str, system_prompt: str, max_retries: int = 2) -> None:
        load_dotenv()
        self._model = model
        self._system_prompt = system_prompt
        self._max_retries = max_retries
        self._client = genai.Client()

    async def evaluate(self, *, checklist: list[str], events_description: str) -> JudgeResult:
        checklist_lines = "\n".join(f"- {item}" for item in checklist) or "- (none)"
        prompt = (
            "Evaluate the events description against the checklist.\n"
            "Checklist items:\n"
            f"{checklist_lines}\n\n"
            "Predicted events description:\n"
            f"{events_description}\n"
        )
        last_error: Exception | None = None
        for _ in range(self._max_retries + 1):
            try:
                response = await self._client.aio.models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=self._system_prompt,
                        response_mime_type="application/json",
                        response_json_schema=_JudgeSchema.model_json_schema(),
                    ),
                )
                parsed = _JudgeSchema.model_validate(response.parsed)
                return JudgeResult(
                    covered_items=parsed.covered_items,
                    contradicted_items=parsed.contradicted_items,
                    rationale=parsed.rationale,
                )
            except Exception as exc:
                last_error = exc
                continue
        assert last_error is not None
        raise last_error


class EventJudge(Protocol):
    async def evaluate(self, *, checklist: list[str], events_description: str) -> JudgeResult: ...


def build_judge(config: JudgeConfig) -> EventJudge:
    if config.provider.kind != "gemini":
        raise ValueError(f"Unsupported judge provider: {config.provider.kind}")
    return GeminiEventJudge(
        model=config.provider.model,
        system_prompt=config.system_prompt,
        max_retries=config.max_retries,
    )
