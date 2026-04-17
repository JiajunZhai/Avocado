"""Extract token counts from OpenAI-compatible chat completion responses."""
from __future__ import annotations

from typing import Any


def total_tokens_from_completion(response: Any) -> int | None:
    """
    Read provider-reported usage (DeepSeek / OpenAI-compatible).
    Returns None if the response has no usable usage block.
    """
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    total = getattr(usage, "total_tokens", None)
    if total is not None:
        try:
            n = int(total)
            return n if n >= 0 else None
        except (TypeError, ValueError):
            pass
    pt = getattr(usage, "prompt_tokens", None)
    ct = getattr(usage, "completion_tokens", None)
    if pt is None and ct is None:
        return None
    try:
        return max(0, int(pt or 0) + int(ct or 0))
    except (TypeError, ValueError):
        return None
