'''
moderation.py -> Image Content Moderation:
- Checks if moderation enabled and key provided
- Converts to base64, calls api
- Reads results, collects the flagged categories with higher scores
- Blocks if flagged, otherwise allows
- Returns response format based on allow/block
'''

from __future__ import annotations
import base64
from dataclasses import dataclass, field
from typing import Dict
from app.config import settings
from openai import OpenAI

#Specific error if moderation is enabled but no api key present
class ModerationConfigError(RuntimeError):
    pass

#The answer format returned, indicated allowed/blocked, scores
@dataclass
class ModerationVerdict:
    allowed: bool       #Allow True/False
    blocked_reason: str | None = None   #Reason when blocked (allowed=False), None otherwise
    scores: Dict[str, float] = field(default_factory=dict)  #per category scores

#OpenAI SDK
def _moderation_client():
    return OpenAI(api_key=settings.MODERATION_API_KEY, base_url="https://api.openai.com/v1")

#Moderates image
def moderate_image(image_bytes: bytes, image_type: str = "image/png") -> ModerationVerdict:
    if not settings.MODERATION_SET:     #checks if Moderation is enabled. If not, then returns Allowed by default
        return ModerationVerdict(allowed=True, scores={"moderation": 0.0})  

    if not settings.MODERATION_API_KEY:     #moderation enabled but no api key
        raise ModerationConfigError("Moderation is enabled but MODERATION_API_KEY is not set. Add an OpenAI API key (the moderation endpoint is free) or set MODERATION_SET=false.")

    
    b64 = base64.standard_b64encode(image_bytes).decode()   #converts to base64
    #calls the api and stores result in resp
    resp = _moderation_client().moderations.create(
        model=settings.MODERATION_MODEL,
        input=[
            {
                "type": "image_url",
                "image_url": {"url": f"data:{image_type};base64,{b64}"},
            }
        ],
    )

    result = resp.results[0]    #takes first from list of output
    scores = dict(result.category_scores)       #per category confidence scores
    over = {cat: score for cat, score in scores.items() if ((score is not None) and (score > settings.MODERATION_THRESHOLD))}   #categories that exceed threshold


    if result.flagged or over:  #if blocked
        worst = max(over, key=over.get) if over else "flagged"      #chooses the category with highest score
        #returns blocked response format
        return ModerationVerdict(
            allowed=False,
            blocked_reason=f"Content blocked by moderation gate (category: {worst})",
            scores=scores,
        )
    #returns allowed response format
    return ModerationVerdict(allowed=True, scores=scores)