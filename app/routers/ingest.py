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
from app.pii import safe_log_payload
from app.schemas import IngestResponse
from app.storage import get_storage
from app.watermark import apply_watermark, resize_for_vision

router = APIRouter()
logger = logging.getLogger("ledgerlens.ingest")
_INGEST_TIMES: list[float] = []

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/jpg"}


@router.post("/ingest", response_model=IngestResponse)
async def ingest_document(
    file: UploadFile = File(...), db: Session = Depends(get_db)
) -> IngestResponse:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(415, detail=f"Unsupported type {file.content_type}; upload JPG or PNG")

    raw = await file.read()
    if not raw:
        raise HTTPException(400, detail="Empty file")

    doc_id = uuid.uuid4().hex[:12]
    filename = file.filename or f"{doc_id}.png"

    t0 = time.perf_counter()
    try:
        verdict = moderate_image(raw, mime=file.content_type)
    except ModerationConfigError as e:
        # Fail loudly rather than silently skipping the safety gate.
        raise HTTPException(503, detail=str(e))
    metrics.MODERATION_LATENCY.observe(time.perf_counter() - t0)

    if not verdict.allowed:
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
        raise HTTPException(422, detail={"doc_id": doc_id, "blocked_reason": verdict.blocked_reason})

    processed = resize_for_vision(raw, settings.MAX_IMAGE_DIM)

    t1 = time.perf_counter()
    result = extract_invoice(processed)
    metrics.EXTRACTION_LATENCY.observe(time.perf_counter() - t1)
    metrics.TOKEN_COST_USD.inc(result.cost_usd)

    status, flagged = route_by_confidence(result.invoice)

    watermarked = apply_watermark(processed, doc_id)
    storage = get_storage()
    image_path = storage.save(doc_id, "watermarked.png", watermarked)

    extracted_json = result.invoice.model_dump_json()
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
            )
        )
    db.commit()

    metrics.DOCS_INGESTED.labels(status=status).inc()
    now = time.time()
    _INGEST_TIMES.append(now)
    while _INGEST_TIMES and now - _INGEST_TIMES[0] > 60:
        _INGEST_TIMES.pop(0)
    metrics.THROUGHPUT_DPM.set(len(_INGEST_TIMES))
    if status == "auto_approved":
        metrics.AUTO_APPROVALS.inc()
    else:
        metrics.PENDING_REVIEW_GAUGE.inc()
    logger.info(
        "doc %s ingested status=%s flagged=%d cost=$%.5f payload=%s",
        doc_id,
        status,
        len(flagged),
        result.cost_usd,
        safe_log_payload(extracted_json),  
    )

    return IngestResponse(
        doc_id=doc_id,
        filename=filename,
        status=status,
        extraction=result.invoice,
        flagged_fields=flagged,
        cost_usd=result.cost_usd,
        watermarked_image_url=f"/image/{doc_id}",
    )
