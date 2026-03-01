import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from vid_analyser.overlay import ZoneDefinition
from vid_analyser.pipeline import OverlayConfig, PersonIdConfig, RunConfig
from vid_analyser.llm.gemini import GeminiProvider


class ProviderConfig(BaseModel):
    kind: Literal["gemini"] = "gemini"
    model: str


class JudgeConfig(BaseModel):
    provider: ProviderConfig
    system_prompt: str
    max_retries: int = Field(default=2, ge=0)


class RunConfigInput(BaseModel):
    provider: ProviderConfig
    overlay_zones: list[ZoneDefinition] = Field(default_factory=list)
    enable_person_id: bool = False

    def to_run_config(self) -> RunConfig:
        if self.provider.kind != "gemini":
            raise ValueError(f"Unsupported analysis provider: {self.provider.kind}")
        overlay = OverlayConfig(zones=self.overlay_zones) if self.overlay_zones else None
        person_id = PersonIdConfig() if self.enable_person_id else None
        return RunConfig(
            provider=GeminiProvider(model=self.provider.model),
            overlay=overlay,
            person_id=person_id,
        )


class EvalConfigInput(BaseModel):
    run_id: str
    run_config: RunConfigInput
    user_prompt: str
    system_prompt: str
    judge: JudgeConfig
    max_concurrency: int = Field(default=4, ge=1)


class EvalConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    run_id: str
    run_config: RunConfig
    user_prompt: str
    system_prompt: str
    judge: JudgeConfig
    max_concurrency: int = Field(default=4, ge=1)
    raw_input: EvalConfigInput

    @classmethod
    def from_json_path(cls, path: str | Path) -> "EvalConfig":
        raw_json = Path(path).read_text(encoding="utf-8")
        raw = EvalConfigInput.model_validate_json(raw_json)
        return cls(
            run_id=raw.run_id,
            run_config=raw.run_config.to_run_config(),
            user_prompt=raw.user_prompt,
            system_prompt=raw.system_prompt,
            judge=raw.judge,
            max_concurrency=raw.max_concurrency,
            raw_input=raw,
        )

    def to_persistable_dict(self) -> dict[str, Any]:
        return json.loads(self.raw_input.model_dump_json())
