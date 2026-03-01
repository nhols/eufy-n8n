import asyncio

import pytest

from vid_analyser.evals.judge import GeminiEventJudge


class _FakeResponse:
    def __init__(self, parsed: dict[str, object]) -> None:
        self.parsed = parsed


def test_judge_retries_and_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    class _FakeModels:
        async def generate_content(self, **kwargs: object) -> _FakeResponse:
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("transient")
            return _FakeResponse(
                {
                    "covered_items": ["x"],
                    "contradicted_items": [],
                    "rationale": "ok",
                }
            )

    class _FakeAio:
        models = _FakeModels()

    class _FakeClient:
        aio = _FakeAio()

    monkeypatch.setattr("vid_analyser.evals.judge.genai.Client", lambda: _FakeClient())
    judge = GeminiEventJudge(model="judge-model", system_prompt="judge prompt", max_retries=2)
    result = asyncio.run(judge.evaluate(checklist=["x"], events_description="x happened"))
    assert calls["count"] == 2
    assert result.covered_items == ["x"]


def test_judge_retries_and_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    class _FakeModels:
        async def generate_content(self, **kwargs: object) -> _FakeResponse:
            calls["count"] += 1
            raise RuntimeError("always bad")

    class _FakeAio:
        models = _FakeModels()

    class _FakeClient:
        aio = _FakeAio()

    monkeypatch.setattr("vid_analyser.evals.judge.genai.Client", lambda: _FakeClient())
    judge = GeminiEventJudge(model="judge-model", system_prompt="judge prompt", max_retries=2)
    with pytest.raises(RuntimeError, match="always bad"):
        asyncio.run(judge.evaluate(checklist=["x"], events_description="x happened"))
    assert calls["count"] == 3
