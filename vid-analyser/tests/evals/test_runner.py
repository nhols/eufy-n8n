import asyncio
from unittest.mock import AsyncMock

import pytest

from vid_analyser.evals.config import EvalConfig, EvalConfigInput, JudgeConfig, ProviderConfig, RunConfigInput
from vid_analyser.evals.model import Golden, TestCase as EvalTestCase
from vid_analyser.evals.report_model import JudgeResult
from vid_analyser.evals.runner import score_events, score_exact_match, score_number_plate, run_eval
from vid_analyser.evals.store import StoreAbc, hash_video
from vid_analyser.llm.response_model import AnalyseResponse
from vid_analyser.pipeline import RunConfig


class _FakeStore(StoreAbc):
    def __init__(self, videos: dict[str, bytes], cases: list[EvalTestCase]) -> None:
        self._videos = videos
        self._cases = cases
        self.saved_results: list[object] = []
        self.saved_run_configs: list[tuple[str, dict[str, object]]] = []
        self.saved_reports: list[tuple[str, object]] = []

    def ls_videos(self) -> list[str]:
        return list(self._videos.keys())

    def get_video(self, key: str) -> bytes:
        return self._videos[key]

    def save_golden_case(self, case: Golden, video: bytes, name: str | None = None) -> None:
        raise NotImplementedError

    def get_labelled_cases(self) -> list[EvalTestCase]:
        return self._cases

    def save_eval_run_config(self, run_id: str, config: dict[str, object]) -> None:
        self.saved_run_configs.append((run_id, config))

    def save_eval_case_result(self, run_id: str, result: object) -> None:
        self.saved_results.append(result)

    def save_eval_report(self, run_id: str, report: object) -> None:
        self.saved_reports.append((run_id, report))


class _DummyProvider:
    name = "dummy"

    async def analyze_video(self, req: object) -> AnalyseResponse:
        raise RuntimeError("not used in tests")


def _config() -> EvalConfig:
    raw_input = EvalConfigInput(
        run_id="test-run",
        run_config=RunConfigInput(provider=ProviderConfig(kind="gemini", model="analysis-model")),
        user_prompt="What is in the video?",
        system_prompt="system",
        judge=JudgeConfig(
            provider=ProviderConfig(kind="gemini", model="judge-model"),
            system_prompt="Judge checklist coverage and contradictions.",
        ),
        max_concurrency=4,
    )
    return EvalConfig(
        run_id=raw_input.run_id,
        run_config=RunConfig(provider=_DummyProvider()),
        user_prompt=raw_input.user_prompt,
        system_prompt=raw_input.system_prompt,
        judge=raw_input.judge,
        max_concurrency=raw_input.max_concurrency,
        raw_input=raw_input,
    )


def test_score_exact_match() -> None:
    assert score_exact_match("yes", "yes") == 1.0
    assert score_exact_match("yes", "no") == 0.0


def test_score_number_plate_normalizes() -> None:
    assert score_number_plate("ab 12-cd", "AB12CD") == 1.0
    assert score_number_plate(None, None) == 1.0
    assert score_number_plate(None, "AB12CD") == 0.0


def test_score_events() -> None:
    assert score_events(2, covered_count=2, contradicted_count=0) == 1.0
    assert score_events(2, covered_count=1, contradicted_count=1) == 0.0
    assert score_events(0, covered_count=0, contradicted_count=0) is None


def test_run_eval_with_fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    video_key = "sample.mp4"
    video_bytes = b"video"
    golden = Golden(
        ir_mode="no",
        parking_spot_status="vacant",
        number_plate="AB12CD",
        event_checklist=["person approaches door", "parcel dropped"],
        send_notification=True,
        people=["Alice"],
    )
    case = EvalTestCase(video_path=video_key, video_hash=hash_video(video_bytes), golden=golden)
    store = _FakeStore(videos={video_key: video_bytes}, cases=[case])

    response = AnalyseResponse(
        ir_mode="no",
        parking_spot_status="vacant",
        number_plate="AB 12-CD",
        events_description="A person approached the door.",
        send_notification=True,
    )

    class _FakeJudge:
        async def evaluate(self, *, checklist: list[str], events_description: str) -> JudgeResult:
            assert checklist == golden.event_checklist
            assert "person" in events_description.lower()
            return JudgeResult(
                covered_items=["person approaches door"],
                contradicted_items=["parcel dropped"],
                rationale="One covered, one contradicted.",
            )

    monkeypatch.setattr("vid_analyser.evals.runner.build_judge", lambda cfg: _FakeJudge())
    monkeypatch.setattr("vid_analyser.evals.runner.run", AsyncMock(return_value=response))

    report = asyncio.run(run_eval(store=store, config=_config()))

    assert report.total_cases == 1
    assert report.successful_cases == 1
    assert report.failed_cases == 0
    result = report.cases[0]
    assert result.scores is not None
    assert result.scores.ir_mode == 1.0
    assert result.scores.parking_spot_status == 1.0
    assert result.scores.send_notification == 1.0
    assert result.scores.number_plate == 1.0
    assert result.scores.events_description == 0.0
    assert result.scores.total == 0.8
    assert result.scores.people_status == "not_scored_mvp"
    assert result.scores.people_score is None
    assert report.average_total_score == 0.8
    assert store.saved_run_configs[0][0] == "test-run"
    assert len(store.saved_results) == 1
    assert store.saved_reports[0][0] == "test-run"


def test_run_eval_records_case_errors_and_continues(monkeypatch: pytest.MonkeyPatch) -> None:
    case1_bytes = b"video1"
    case2_bytes = b"video2"
    case1 = EvalTestCase(
        video_path="a.mp4",
        video_hash=hash_video(case1_bytes),
        golden=Golden(
            ir_mode="no",
            parking_spot_status="vacant",
            number_plate=None,
            event_checklist=[],
            send_notification=False,
            people=[],
        ),
    )
    case2 = EvalTestCase(
        video_path="b.mp4",
        video_hash=hash_video(case2_bytes),
        golden=Golden(
            ir_mode="yes",
            parking_spot_status="occupied",
            number_plate="AB12",
            event_checklist=[],
            send_notification=True,
            people=[],
        ),
    )
    store = _FakeStore(
        videos={"a.mp4": case1_bytes, "b.mp4": case2_bytes},
        cases=[case1, case2],
    )
    ok_response = AnalyseResponse(
        ir_mode="yes",
        parking_spot_status="occupied",
        number_plate="AB12",
        events_description="car parked",
        send_notification=True,
    )

    async def _fake_run(*args: object, **kwargs: object) -> AnalyseResponse:
        if _fake_run.calls == 0:
            _fake_run.calls += 1
            raise RuntimeError("boom")
        _fake_run.calls += 1
        return ok_response

    _fake_run.calls = 0

    monkeypatch.setattr("vid_analyser.evals.runner.build_judge", lambda cfg: object())
    monkeypatch.setattr("vid_analyser.evals.runner.run", _fake_run)

    report = asyncio.run(run_eval(store=store, config=_config()))

    assert report.total_cases == 2
    assert report.successful_cases == 1
    assert report.failed_cases == 1
    assert report.cases[0].error == "boom"
    assert report.cases[0].scores is None
    assert report.cases[1].scores is not None
    assert len(store.saved_results) == 2
    assert len(store.saved_reports) == 1


def test_run_eval_empty_store_returns_empty_report(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _FakeStore(videos={}, cases=[])
    called = {"judge": False}

    def _build_judge(_: object) -> object:
        called["judge"] = True
        return object()

    monkeypatch.setattr("vid_analyser.evals.runner.build_judge", _build_judge)
    report = asyncio.run(run_eval(store=store, config=_config()))
    assert called["judge"] is False
    assert report.total_cases == 0
    assert report.successful_cases == 0
    assert report.failed_cases == 0
    assert report.average_total_score is None
    assert len(store.saved_run_configs) == 1
    assert len(store.saved_reports) == 1


def test_run_eval_respects_max_concurrency(monkeypatch: pytest.MonkeyPatch) -> None:
    case_count = 6
    videos = {f"{i}.mp4": f"video-{i}".encode() for i in range(case_count)}
    cases = [
        EvalTestCase(
            video_path=f"{i}.mp4",
            video_hash=hash_video(videos[f"{i}.mp4"]),
            golden=Golden(
                ir_mode="no",
                parking_spot_status="vacant",
                number_plate=None,
                event_checklist=[],
                send_notification=False,
                people=[],
            ),
        )
        for i in range(case_count)
    ]
    store = _FakeStore(videos=videos, cases=cases)

    max_seen = {"value": 0}
    in_flight = {"value": 0}

    async def _fake_run(*args: object, **kwargs: object) -> AnalyseResponse:
        in_flight["value"] += 1
        max_seen["value"] = max(max_seen["value"], in_flight["value"])
        await asyncio.sleep(0.01)
        in_flight["value"] -= 1
        return AnalyseResponse(
            ir_mode="no",
            parking_spot_status="vacant",
            number_plate=None,
            events_description="quiet",
            send_notification=False,
        )

    cfg = _config().model_copy(update={"max_concurrency": 2})
    monkeypatch.setattr("vid_analyser.evals.runner.build_judge", lambda cfg: object())
    monkeypatch.setattr("vid_analyser.evals.runner.run", _fake_run)

    report = asyncio.run(run_eval(store=store, config=cfg))
    assert report.total_cases == case_count
    assert max_seen["value"] <= 2
    assert len(store.saved_results) == case_count
