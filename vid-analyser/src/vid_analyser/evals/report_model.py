from datetime import UTC, datetime

from pydantic import BaseModel, Field
from vid_analyser.evals.config import EvalConfigInput
from vid_analyser.evals.model import Golden
from vid_analyser.llm.response_model import AnalyseResponse


class JudgeResult(BaseModel):
    covered_items: list[str]
    contradicted_items: list[str]
    rationale: str


class CaseScores(BaseModel):
    ir_mode: float
    parking_spot_status: float
    send_notification: float
    number_plate: float
    events_description: float | None
    people_score: float | None = None
    people_status: str = "not_scored_mvp"
    total: float | None


class CaseResult(BaseModel):
    video_path: str
    video_hash: str
    golden: Golden
    prediction: AnalyseResponse | None
    scores: CaseScores | None
    judge: JudgeResult | None
    error: str | None = None


class EvalReport(BaseModel):
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    total_cases: int
    successful_cases: int
    failed_cases: int
    average_total_score: float | None
    cases: list[CaseResult]


class EvalRunRecord(BaseModel):
    run_id: str
    report: EvalReport
    config: EvalConfigInput | None = None


class RunOverviewRow(BaseModel):
    run_id: str
    created_at: datetime
    average_total_score: float | None
    successful_cases: int
    failed_cases: int
    analysis_model: str | None
    judge_model: str | None


class EvalCaseRow(BaseModel):
    run_id: str
    video_path: str
    video_hash: str
    total_score: float | None
    ir_mode_score: float | None
    parking_spot_status_score: float | None
    send_notification_score: float | None
    number_plate_score: float | None
    events_description_score: float | None
    error: str | None
    case_result: CaseResult
