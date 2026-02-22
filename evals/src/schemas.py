"""Pydantic schemas for the eval framework."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# --- Model output schema (mirrors Gemini responseSchema) ---


class IrMode(str, Enum):
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


class ParkingSpotStatus(str, Enum):
    OCCUPIED = "occupied"
    VACANT = "vacant"
    CAR_ENTERING = "car entering"
    CAR_LEAVING = "car leaving"
    UNKNOWN = "unknown"


class ModelOutput(BaseModel):
    """Structured output returned by the video-analysis model."""

    ir_mode: IrMode
    parking_spot_status: ParkingSpotStatus
    number_plate: str | None
    events_description: str
    summary: str
    send_notification: bool


# --- Test case schema ---


class JudgeCriteria(BaseModel):
    """Per-field criteria the LLM judge checks for presence of."""

    events_description: list[str] = Field(default_factory=list)


class ExpectedOutput(BaseModel):
    """Ground-truth values for exact-match fields."""

    ir_mode: IrMode
    parking_spot_status: ParkingSpotStatus
    number_plate: str | None = None
    send_notification: bool


class Booking(BaseModel):
    """A single parking booking in the format injected into the system prompt."""

    driver_name: str
    start_time: str
    end_time: str
    vehicle_make: str
    vehicle_model: str
    vehicle_colour: str
    vehicle_registration: str


class TestCaseMetadata(BaseModel):
    """Context injected into the system prompt at runtime."""

    local_datetime: str
    bookings: list[Booking] = Field(default_factory=list)


class TestCase(BaseModel):
    """A single evaluation example."""

    id: str
    video_path: str
    metadata: TestCaseMetadata
    expected: ExpectedOutput
    judge_criteria: JudgeCriteria = Field(default_factory=JudgeCriteria)


# --- Eval config schema ---


class JudgeConfig(BaseModel):
    """Configuration for the LLM-as-judge."""

    provider: str = "gemini"
    model: str = "gemini-2.0-flash"
    params: dict[str, Any] = Field(default_factory=lambda: {"temperature": 0.0})


class EvalConfig(BaseModel):
    """A full evaluation configuration to test."""

    name: str
    provider: str
    model: str
    system_prompt_path: str
    generation_params: dict[str, Any] = Field(default_factory=dict)
    iterations: int = 3
    judge: JudgeConfig = Field(default_factory=JudgeConfig)


# --- Result schemas ---


class FieldScores(BaseModel):
    """Per-field scores for a single run."""

    ir_mode: float = 0.0
    parking_spot_status: float = 0.0
    number_plate: float = 0.0
    number_plate_null_accuracy: float = 0.0
    events_description: float = 0.0
    send_notification: float = 0.0


class JudgeDetail(BaseModel):
    """Detailed judge results for free-text fields."""

    events_description_score: float = 0.0


class TokenUsage(BaseModel):
    """Token counts from a model call."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class GenerateResult(BaseModel):
    """Wraps model output together with token usage metadata."""

    output: ModelOutput
    token_usage: TokenUsage = Field(default_factory=TokenUsage)


class RunResult(BaseModel):
    """Result of a single model invocation."""

    config_name: str
    test_case_id: str
    iteration: int
    model_output: ModelOutput
    scores: FieldScores
    judge_detail: JudgeDetail = Field(default_factory=JudgeDetail)
    latency_ms: float
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    error: str | None = None


class AggregateScores(BaseModel):
    """Mean and std scores across iterations."""

    ir_mode_mean: float = 0.0
    ir_mode_std: float = 0.0
    parking_spot_status_mean: float = 0.0
    parking_spot_status_std: float = 0.0
    number_plate_mean: float = 0.0
    number_plate_std: float = 0.0
    number_plate_null_accuracy_mean: float = 0.0
    number_plate_null_accuracy_std: float = 0.0
    events_description_mean: float = 0.0
    events_description_std: float = 0.0
    send_notification_mean: float = 0.0
    send_notification_std: float = 0.0


class EvalReport(BaseModel):
    """Full report for one eval config run."""

    config: EvalConfig
    results: list[RunResult]
    aggregate_scores: dict[str, AggregateScores] = Field(default_factory=dict)
    overall_scores: AggregateScores = Field(default_factory=AggregateScores)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
