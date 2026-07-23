from __future__ import annotations
import base64
from dataclasses import dataclass, field
from typing import Dict
from app.config import settings
from openai import OpenAI

class ModerationConfigError(RuntimeError):
    pass

@dataclass
class ModerationVerdict:
    allowed: bool
    blocked_reason: str | None = None
    scores: Dict[str, float] = field(default_factory=dict)

def _moderation_client():
    return OpenAI(api_key=settings.MODERATION_API_KEY)


def moderate_image(image_bytes: bytes, mime: str = "image/png") -> ModerationVerdict:
    """Screen an image; return an allow/block verdict with category scores."""
    if not settings.MODERATION_ENABLED:
        return ModerationVerdict(allowed=True, scores={"moderation": 0.0})

    if not settings.MODERATION_API_KEY:
        raise ModerationConfigError(
            "Moderation is enabled but MODERATION_API_KEY is not set. "
            "Add an OpenAI API key (the moderation endpoint is free) or set "
            "MODERATION_ENABLED=false."
        )

    b64 = base64.standard_b64encode(image_bytes).decode()
    resp = _moderation_client().moderations.create(
        model=settings.MODERATION_MODEL,
        input=[
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}"},
            }
        ],
    )

    result = resp.results[0]
    scores = dict(result.category_scores)
    over = {
        cat: score
        for cat, score in scores.items()
        if score is not None and score > settings.MODERATION_THRESHOLD
    }

    if result.flagged or over:
        worst = max(over, key=over.get) if over else "flagged"
        return ModerationVerdict(
            allowed=False,
            blocked_reason=f"Content blocked by moderation gate (category: {worst})",
            scores=scores,
        )

    return ModerationVerdict(allowed=True, scores=scores)