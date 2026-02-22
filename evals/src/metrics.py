"""Scoring functions for eval fields."""

from __future__ import annotations

from rapidfuzz.distance import Levenshtein


def exact_match(predicted: str | bool, expected: str | bool) -> float:
    """Return 1.0 if values match exactly, else 0.0.

    Works for enums (compared as strings) and booleans.
    """
    if isinstance(predicted, bool) and isinstance(expected, bool):
        return 1.0 if predicted == expected else 0.0
    return 1.0 if str(predicted).strip().lower() == str(expected).strip().lower() else 0.0


def null_accuracy(predicted: str | None, expected: str | None) -> float:
    """Return 1.0 if both are null or both are non-null, else 0.0.

    Isolates the "did the model detect a plate at all?" question
    from the "did it read the plate correctly?" question.
    """
    pred_is_null = predicted is None or str(predicted).strip().lower() in ("", "null", "none")
    exp_is_null = expected is None or str(expected).strip().lower() in ("", "null", "none")
    return 1.0 if pred_is_null == exp_is_null else 0.0


def number_plate_score(predicted: str | None, expected: str | None) -> float:
    """Score number plate predictions using normalised Levenshtein similarity.

    - Both null → 1.0
    - One null, other not → 0.0
    - Both strings → 1 - (levenshtein_distance / max_len), ignoring spaces and case
    """
    pred_is_null = predicted is None or str(predicted).strip().lower() in ("", "null", "none")
    exp_is_null = expected is None or str(expected).strip().lower() in ("", "null", "none")

    if pred_is_null and exp_is_null:
        return 1.0
    if pred_is_null != exp_is_null:
        return 0.0

    # Both are non-null strings — normalise
    p = str(predicted).strip().upper().replace(" ", "")
    e = str(expected).strip().upper().replace(" ", "")

    if not p and not e:
        return 1.0

    max_len = max(len(p), len(e))
    if max_len == 0:
        return 1.0

    dist = Levenshtein.distance(p, e)
    return 1.0 - (dist / max_len)
