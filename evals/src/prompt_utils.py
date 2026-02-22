"""Utility to load and template system prompts."""

from __future__ import annotations

import json
from pathlib import Path

from evals.src.schemas import TestCaseMetadata


def load_and_template_prompt(prompt_path: str, metadata: TestCaseMetadata) -> str:
    """Load a system prompt file and replace n8n template expressions
    with actual test-case metadata values.

    Handles the {{ $json.local_datetime }} and {{ $json.bookings }} placeholders
    used in the production sys_prompt.md.
    """
    text = Path(prompt_path).read_text()

    # Serialize bookings to compact JSON string (matches n8n injection format)
    bookings_str = (
        json.dumps(
            [b.model_dump() for b in metadata.bookings],
        )
        if metadata.bookings
        else "No bookings today."
    )

    replacements = {
        "{{ $json.local_datetime }}": metadata.local_datetime,
        "{{ $json.bookings }}": bookings_str,
        # Also handle without spaces
        "{{$json.local_datetime}}": metadata.local_datetime,
        "{{$json.bookings}}": bookings_str,
    }

    for placeholder, value in replacements.items():
        text = text.replace(placeholder, value)

    return text
