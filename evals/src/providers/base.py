"""Abstract base class for model providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from evals.src.schemas import GenerateResult


class Provider(ABC):
    """Interface for video-analysis model providers."""

    def __init__(self, model: str, generation_params: dict[str, Any] | None = None):
        self.model = model
        self.generation_params = generation_params or {}

    @abstractmethod
    async def generate(
        self,
        video_bytes: bytes,
        system_prompt: str,
        generation_params: dict[str, Any] | None = None,
    ) -> GenerateResult:
        """Send video + prompt to the model and return structured output.

        Args:
            video_bytes: Raw MP4 file bytes.
            system_prompt: The fully-templated system prompt.
            generation_params: Override generation params for this call.

        Returns:
            GenerateResult containing parsed ModelOutput and token usage.
        """
        ...
