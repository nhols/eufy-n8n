import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from vid_analyser.evals.model import Golden, TestCase
from vid_analyser.evals.report_model import CaseResult, EvalReport
from vid_analyser.evals.store import StoreAbc, hash_video

VIDEOS = "videos"
GOLDEN = "golden"
EVAL_RUNS = "eval_runs"
CASES = "cases"
CONFIG_JSON = "config.json"
REPORT_JSON = "report.json"


class LocalStore(StoreAbc):
    def __init__(self, root: str | Path = "_evals") -> None:
        self.root = Path(root)
        self.videos_dir = self.root / VIDEOS
        self.golden_dir = self.root / GOLDEN
        self.eval_runs_dir = self.root / EVAL_RUNS
        self.videos_dir.mkdir(parents=True, exist_ok=True)
        self.golden_dir.mkdir(parents=True, exist_ok=True)
        self.eval_runs_dir.mkdir(parents=True, exist_ok=True)

    def ls_videos(self) -> list[str]:
        return sorted(str(path.relative_to(self.videos_dir)) for path in self.videos_dir.rglob("*") if path.is_file())

    def get_video(self, key: str) -> bytes:
        return (self.videos_dir / key).read_bytes()

    def save_golden_case(self, case: Golden, video: bytes, name: str | None = None) -> None:
        name = name or f"{uuid4()}.mp4"
        if not name.endswith(".mp4"):
            raise ValueError("Name must end with .mp4")

        rel_video_path = Path(name)
        video_path = self.videos_dir / rel_video_path
        video_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.write_bytes(video)

        test_case = TestCase(
            video_path=rel_video_path.as_posix(),
            video_hash=hash_video(video),
            golden=case,
        )

        golden_path = self.golden_dir / rel_video_path.with_suffix(".json")
        golden_path.parent.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(test_case.model_dump_json(indent=2), encoding="utf-8")

    def get_labelled_cases(self) -> list[TestCase]:
        return [
            TestCase.model_validate_json(json_path.read_text(encoding="utf-8"))
            for json_path in sorted(self.golden_dir.rglob("*.json"))
        ]

    def _run_dir(self, run_id: str) -> Path:
        run_dir = self.eval_runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def save_eval_run_config(self, run_id: str, config: dict[str, Any]) -> None:
        run_dir = self._run_dir(run_id)
        config_path = run_dir / CONFIG_JSON
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    def save_eval_case_result(self, run_id: str, result: CaseResult) -> None:
        run_dir = self._run_dir(run_id)
        cases_dir = run_dir / CASES
        cases_dir.mkdir(parents=True, exist_ok=True)
        case_path = cases_dir / f"{result.video_hash}.json"
        case_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")

    def save_eval_report(self, run_id: str, report: EvalReport) -> None:
        run_dir = self._run_dir(run_id)
        report_path = run_dir / REPORT_JSON
        report_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
