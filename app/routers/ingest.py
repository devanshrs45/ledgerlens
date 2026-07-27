'''
ingest.py -> Full pipeline:
- Reads File and handles edge cases, Creates file id
- Moderation of image
- Extraction of text
- Confidence routing
- Watermark adding
- Storage and saving watermarked image
- Metrics to measure throughtput/status
- Logging and PII redaction
- Returns the final extraction result
'''

from __future__ import annotations
import logging
import time
import uuid
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from app import metrics
from app.config import settings
from app.database import Document, ReviewQueueItem, get_db
from app.extraction import extract_invoice, route_by_confidence
from app.moderation import ModerationConfigError, moderate_image
from app.pii import redact_all_pii
from app.schemas import ExtractionResult
from app.storage import get_storage
from app.watermark import add_visible_watermark, resize_image


router = APIRouter()    #FastAPI to group routes
logger = logging.getLogger("onrecord.ingest")   #a loggerwith a name
_INGEST_TIMES: list[float] = [] #list of timestamps
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/jpg"}    #allowed image types

#/ingest as post, return value as ExtractionResult schema
@router.post("/ingest", response_model=ExtractionResult)
async def ingest_document(file: UploadFile = File(...), db: Session = Depends(get_db)) -> ExtractionResult:
    if file.content_type not in ALLOWED_TYPES:  #if file type not allowed
        raise HTTPException(415, detail=f"Unsupported type {file.content_type}; upload JPG or PNG")

    raw = await file.read()     #raw bytes of file
    if not raw:     #for empty upload
        raise HTTPException(400, detail="Empty file")

    doc_id = uuid.uuid4().hex[:12]      #Document ID, in everything
    filename = file.filename or f"{doc_id}.png"     #image filename

    #Moderation, before extraction
    t0 = time.perf_counter()    #for latency
    try:        #if moderation enabled but no key
        verdict = moderate_image(raw, image_type=file.content_type)
    except ModerationConfigError as e:
        # Fail loudly rather than silently skipping the safety gate.
        raise HTTPException(503, detail=str(e))
    metrics.MODERATION_LATENCY.observe(time.perf_counter() - t0)

    if not verdict.allowed:     #if image blocked
        db.add(
            Document(
                id=doc_id,
                filename=filename,
                status="blocked",
                blocked_reason=verdict.blocked_reason,
            )
        )
        db.commit()
        metrics.DOCS_INGESTED.labels(status="blocked").inc()
        logger.warning("doc %s blocked: %s", doc_id, verdict.blocked_reason)
        raise HTTPException(422, detail={"doc_id": doc_id, "blocked_reason": verdict.blocked_reason})   #raises 422, so no extraction/llm call happens

    #Image moderation allowed ->

    processed = resize_image(raw, settings.IMAGE_DIM)   #resize image

    #Extraction
    t1 = time.perf_counter()    #latency
    result = extract_invoice(processed)     #ExtractOutput
    metrics.EXTRACTION_LATENCY.observe(time.perf_counter() - t1)    #latency
    metrics.TOKEN_COST_USD.inc(result.cost_usd)     #cost

    status, flagged = route_by_confidence(result.invoice)   #checks confidence, returns a status (auto-approve, review) and flag list (if review)

    watermarked = add_visible_watermark(processed, doc_id)  #adds visible watermark
    storage = get_storage()     #gets the storage, local or s3
    image_path = storage.save(doc_id, "watermarked.png", watermarked)   #saves the watermarked image to storage


    extracted_json = result.invoice.model_dump_json()   #json string
    db.add(
        Document(
            id=doc_id,
            filename=filename,
            status=status,
            extracted_json=extracted_json,
            image_path=image_path,
            cost_usd=result.cost_usd,
        )
    )
    for f in flagged:
        db.add(
            ReviewQueueItem(
                id=uuid.uuid4().hex[:12],
                doc_id=doc_id,
                field_path=f.field_path,
                value=f.value,
                confidence=f.confidence,
                reason=f.reason
            )
        )
    db.commit() #writes everything

    #throughput metrics
    metrics.DOCS_INGESTED.labels(status=status).inc()
    now = time.time()
    _INGEST_TIMES.append(now)
    while _INGEST_TIMES and now - _INGEST_TIMES[0] > 60:
        _INGEST_TIMES.pop(0)
    metrics.THROUGHPUT_DPM.set(len(_INGEST_TIMES))

    #document status metrics
    if status == "auto_approved":
        metrics.AUTO_APPROVALS.inc()
    else:
        metrics.PENDING_REVIEW_GAUGE.inc()

    #logs the result, redacts pii    
    logger.info(
        "doc %s ingested status=%s flagged=%d cost=$%.5f payload=%s",
        doc_id,
        status,
        len(flagged),
        result.cost_usd,
        redact_all_pii(extracted_json),  
    )

    #returns exraction result
    return ExtractionResult(
        doc_id=doc_id,
        filename=filename,
        status=status,
        extraction=result.invoice,
        flagged_fields=flagged,
        cost_usd=result.cost_usd,
        watermarked_image_url=f"/image/{doc_id}",
    )
