from __future__ import annotations
import json
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from app import metrics
from app.database import Document, ReviewQueueItem, get_db
from app.schemas import ApproveRequest, ApproveResponse, DocumentSummary, FlaggedField, InvoiceSchema, ReviewItem, RejectRequest, RejectResponse
from app.storage import get_storage


router = APIRouter()
logger = logging.getLogger("ledgerlens.review")

@router.get("/review", response_model=List[ReviewItem])
def get_review_queue(db: Session = Depends(get_db)) -> List[ReviewItem]:
    docs = (
        db.query(Document)
        .filter(Document.status == "pending_review")
        .order_by(Document.created_at.asc())
        .all()
    )
    items: List[ReviewItem] = []
    for doc in docs:
        try:
            extraction = InvoiceSchema.model_validate_json(doc.extracted_json)
        except Exception:
            logger.warning("doc %s has an incompatible extraction schema, skipping", doc.id)
            continue
        flagged_rows = (
            db.query(ReviewQueueItem)
            .filter(ReviewQueueItem.doc_id == doc.id, ReviewQueueItem.status == "pending")
            .all()
        )
        items.append(
            ReviewItem(
                doc_id=doc.id,
                filename=doc.filename,
                created_at=doc.created_at,
                extraction=extraction,
                flagged_fields=[
                    FlaggedField(
                        field_path=r.field_path, value=r.value, confidence=r.confidence
                    )
                    for r in flagged_rows
                ],
                watermarked_image_url=f"/image/{doc.id}",
            )
        )
    return items


def _apply_correction(data: dict, field_path: str, corrected: str) -> bool:
    if field_path.startswith("line_items["):
        idx = int(field_path.split("[")[1].rstrip("]"))
        if 0 <= idx < len(data.get("line_items", [])):
            data["line_items"][idx]["description"] = corrected
            data["line_items"][idx]["confidence"] = 1.0
            return True
        return False

    node = data.get(field_path)
    if not isinstance(node, dict):
        return False

    if isinstance(node.get("value"), (int, float)):
        try:
            node["value"] = float(corrected)
        except ValueError:
            return False
    else:
        node["value"] = corrected

    node["confidence"] = 1.0 
    return True


@router.post("/approve", response_model=ApproveResponse)
def approve_document(req: ApproveRequest, db: Session = Depends(get_db)) -> ApproveResponse:
    doc = db.query(Document).filter(Document.id == req.doc_id).first()
    if not doc:
        raise HTTPException(404, detail="Document not found")
    if doc.status not in ("pending_review", "auto_approved"):
        raise HTTPException(409, detail=f"Document is in state '{doc.status}'")
    data = json.loads(doc.extracted_json)
    applied = 0
    for corr in req.corrections:
        if _apply_correction(data, corr.field_path, corr.corrected_value):
            applied += 1
            row = (
                db.query(ReviewQueueItem)
                .filter(
                    ReviewQueueItem.doc_id == req.doc_id,
                    ReviewQueueItem.field_path == corr.field_path,
                )
                .first()
            )
            if row:
                row.status = "corrected"
                row.corrected_value = corr.corrected_value

    db.query(ReviewQueueItem).filter(
        ReviewQueueItem.doc_id == req.doc_id, ReviewQueueItem.status == "pending"
    ).update({"status": "approved"})
    was_pending = doc.status == "pending_review"
    doc.reviewed_json = json.dumps(data)
    doc.status = "approved"
    db.commit()
    if was_pending:
        metrics.PENDING_REVIEW_GAUGE.dec()
    metrics.REVIEWS_COMPLETED.inc()
    logger.info("doc %s approved with %d corrections", req.doc_id, applied)
    return ApproveResponse(doc_id=req.doc_id, status="approved", applied_corrections=applied)



@router.get("/documents", response_model=List[DocumentSummary])
def list_documents(limit: int = 50, db: Session = Depends(get_db)) -> List[DocumentSummary]:
    docs = db.query(Document).order_by(Document.created_at.desc()).limit(limit).all()
    out: List[DocumentSummary] = []
    for d in docs:
        vendor = total = currency = None
        extraction = None
        source = d.reviewed_json or d.extracted_json

        if source:
            data = json.loads(source)
            vendor = data.get("vendor", {}).get("value")
            total = data.get("total", {}).get("value")
            currency = data.get("currency", {}).get("value")
            try:
                extraction = InvoiceSchema(**data)
            except Exception:
                extraction = None  # older record, schema has moved on

        out.append(
            DocumentSummary(
                doc_id=d.id,
                filename=d.filename,
                status=d.status,
                vendor=vendor,
                total=total,
                currency=currency,
                created_at=d.created_at,
                cost_usd=d.cost_usd or 0.0,
                blocked_reason=d.blocked_reason,
                extraction=extraction,
            )
        )
        
    return out


@router.get("/image/{doc_id}")
def get_image(doc_id: str, db: Session = Depends(get_db)) -> Response:
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc or not doc.image_path:
        raise HTTPException(404, detail="Image not found")
    storage = get_storage()
    if not storage.exists(doc.image_path):
        raise HTTPException(404, detail="Image file missing from storage")
    
    return Response(content=storage.load(doc.image_path), media_type="image/png")


@router.post("/reject", response_model=RejectResponse)
def reject_document(req: RejectRequest, db: Session = Depends(get_db)) -> RejectResponse:
    doc = db.query(Document).filter(Document.id == req.doc_id).first()
    if not doc:
        raise HTTPException(404, detail="Document not found")
    if doc.status not in ("pending_review", "auto_approved"):
        raise HTTPException(409, detail=f"Document is in state '{doc.status}'")

    was_pending = doc.status == "pending_review"
    doc.status = "rejected"
    doc.blocked_reason = req.reason or "Rejected by reviewer"
    db.query(ReviewQueueItem).filter(
        ReviewQueueItem.doc_id == req.doc_id, ReviewQueueItem.status == "pending"
    ).update({"status": "rejected"})
    db.commit()

    if was_pending:
        metrics.PENDING_REVIEW_GAUGE.dec()
    logger.info("doc %s rejected: %s", req.doc_id, doc.blocked_reason)
    return RejectResponse(doc_id=req.doc_id, status="rejected")