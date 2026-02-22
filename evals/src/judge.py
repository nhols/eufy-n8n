"""LLM-as-judge for evaluating free-text fields."""

from __future__ import annotations

import json
import os
from typing import Any

from google import genai
from google.genai import types
from google.genai.errors import ClientError
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter

from evals.src.schemas import JudgeConfig


def _is_rate_limit_error(exc: BaseException) -> bool:
    return isinstance(exc, ClientError) and exc.code == 429

JUDGE_SYSTEM_PROMPT = """\
You are an evaluation judge. Given a piece of text and a list of required \
information points, score the text on a scale from 0.0 to 1.0.

Scoring guide:
- 1.0: The text contains ALL required information points.
- 0.7-0.9: The text contains most required information with no contradictory \
statements.
- 0.3-0.6: The text is missing some required information OR contains minor \
inaccuracies.
- 0.0-0.2: The text contains contradictory information relative to the \
required points, OR is missing most required information.

IMPORTANT: Any statement that contradicts the required information points is a \
serious penalty. A text with contradictions should never score above 0.3.

Return ONLY a JSON object with a single key "score" mapped to a float between \
0.0 and 1.0. No extra keys, no explanation.
"""

JUDGE_USER_TEMPLATE = """\
Text to evaluate:
\"\"\"
{text}
\"\"\"

Required information:
{criteria_json}
"""


def _build_gemini_client(api_key: str | None = None) -> genai.Client:
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ValueError("GEMINI_API_KEY required for judge")
    return genai.Client(api_key=key)


def judge_text(
    text: str,
    criteria: list[str],
    judge_config: JudgeConfig,
) -> float:
    """Use an LLM to produce a holistic 0-1 score for the text.

    Args:
        text: The model-generated text to evaluate.
        criteria: List of required information points.
        judge_config: Provider/model/params for the judge.

    Returns:
        A float score between 0.0 and 1.0.
    """
    if not criteria:
        return 1.0

    user_prompt = JUDGE_USER_TEMPLATE.format(
        text=text,
        criteria_json=json.dumps(criteria, indent=2),
    )

    if judge_config.provider == "gemini":
        result = _judge_with_gemini(user_prompt, judge_config)
    elif judge_config.provider == "openai":
        result = _judge_with_openai(user_prompt, judge_config)
    else:
        raise ValueError(f"Unsupported judge provider: {judge_config.provider}")

    score = float(result.get("score", 0.0))
    return max(0.0, min(1.0, score))


@retry(
    retry=retry_if_exception(_is_rate_limit_error),
    wait=wait_exponential_jitter(initial=2, max=60),
    stop=stop_after_attempt(6),
    reraise=True,
)
def _judge_with_gemini(
    user_prompt: str,
    judge_config: JudgeConfig,
) -> dict[str, int]:
    client = _build_gemini_client()
    params = dict(judge_config.params)

    config = types.GenerateContentConfig(
        system_instruction=JUDGE_SYSTEM_PROMPT,
        response_mime_type="application/json",
        **params,
    )

    response = client.models.generate_content(
        model=judge_config.model,
        contents=[user_prompt],
        config=config,
    )
    return json.loads(response.text)


def _judge_with_openai(
    user_prompt: str,
    judge_config: JudgeConfig,
) -> dict[str, int]:
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY required for OpenAI judge")

    client = OpenAI(api_key=api_key)
    params = dict(judge_config.params)

    response = client.chat.completions.create(
        model=judge_config.model,
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        **params,
    )
    return json.loads(response.choices[0].message.content)



