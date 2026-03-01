import json
from pathlib import Path

from vid_analyser.evals.config import EvalConfigInput, JudgeConfig, ProviderConfig, RunConfigInput
from vid_analyser.evals.model import Golden
from vid_analyser.evals.report_model import CaseResult, CaseScores, EvalCaseRow, EvalReport, EvalRunRecord
from vid_analyser.evals.store.local import LocalStore
from vid_analyser.evals.ui.results.app import (
    filter_case_rows,
    flatten_case_rows,
    load_runs,
    load_video_bytes,
)
from vid_analyser.llm.response_model import AnalyseResponse


def _case_result(video_path: str, video_hash: str, total: float, error: str | None = None) -> CaseResult:
    return CaseResult(
        video_path=video_path,
        video_hash=video_hash,
        golden=Golden(
            ir_mode="no",
            parking_spot_status="vacant",
            number_plate=None,
            event_checklist=["person leaves house"],
            send_notification=True,
            people=[],
        ),
        prediction=AnalyseResponse(
            ir_mode="no",
            parking_spot_status="vacant",
            number_plate=None,
            events_description="A person leaves the house.",
            send_notification=True,
        ),
        scores=CaseScores(
            ir_mode=1.0,
            parking_spot_status=1.0,
            send_notification=1.0,
            number_plate=1.0,
            events_description=total,
            total=total,
        ),
        judge=None,
        error=error,
    )


def _report(*cases: CaseResult) -> EvalReport:
    return EvalReport(
        total_cases=len(cases),
        successful_cases=sum(1 for case in cases if case.error is None),
        failed_cases=sum(1 for case in cases if case.error is not None),
        average_total_score=sum(case.scores.total for case in cases if case.scores and case.scores.total is not None)
        / len(cases),
        cases=list(cases),
    )


def _config_input(model: str) -> EvalConfigInput:
    return EvalConfigInput(
        run_id=f"{model}-run",
        run_config=RunConfigInput(provider=ProviderConfig(kind="gemini", model=model)),
        user_prompt="What is in the video?",
        system_prompt="system",
        judge=JudgeConfig(provider=ProviderConfig(kind="gemini", model=f"{model}-judge")),
        max_concurrency=4,
    )


def test_load_runs_loads_valid_runs_and_tolerates_missing_config(tmp_path: Path) -> None:
    store = LocalStore(root=tmp_path)
    run1 = store.eval_runs_dir / "run1"
    run1.mkdir(parents=True)
    (run1 / "report.json").write_text(_report(_case_result("a.mp4", "ha", 0.8)).model_dump_json(), encoding="utf-8")
    (run1 / "config.json").write_text(
        _config_input("m1").model_dump_json(),
        encoding="utf-8",
    )

    run2 = store.eval_runs_dir / "run2"
    run2.mkdir(parents=True)
    (run2 / "report.json").write_text(_report(_case_result("b.mp4", "hb", 0.7)).model_dump_json(), encoding="utf-8")

    ignored = store.eval_runs_dir / "ignored"
    ignored.mkdir(parents=True)

    runs = load_runs(store)

    assert [run.run_id for run in runs] == ["run2", "run1"] or [run.run_id for run in runs] == ["run1", "run2"]
    by_id = {run.run_id: run.config for run in runs}
    assert isinstance(by_id["run1"], EvalConfigInput)
    assert by_id["run2"] is None


def test_flatten_filter_and_select_case_rows(tmp_path: Path) -> None:
    report1 = _report(_case_result("a.mp4", "ha", 0.8), _case_result("b.mp4", "hb", 0.4))
    report2 = _report(_case_result("a.mp4", "ha", 0.9))
    runs = [
        EvalRunRecord(run_id="run1", report=report1, config=_config_input("m1")),
        EvalRunRecord(run_id="run2", report=report2, config=None),
    ]

    rows = flatten_case_rows(runs)
    assert len(rows) == 3
    assert all(isinstance(row, EvalCaseRow) for row in rows)

    filtered = filter_case_rows(rows, ["run1", "run2"])
    assert len(filtered) == 3

    selected = filtered[0]
    assert selected.run_id == "run1"
    assert selected.video_path == "a.mp4"


def test_load_video_bytes_returns_none_for_missing_video(tmp_path: Path) -> None:
    store = LocalStore(root=tmp_path)
    video_path = "clip.mp4"
    (store.videos_dir / video_path).write_bytes(b"video-bytes")

    assert load_video_bytes(store, video_path) == b"video-bytes"
    assert load_video_bytes(store, "missing.mp4") is None
