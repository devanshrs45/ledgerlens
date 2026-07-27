'''
review.py -> Human Review Receipts:
- Review Queue, Apply Corrections, Approve/Reject document
- List all Documents
- Get Image
'''

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

router = APIRouter()    #FastAPI to group routes
logger = logging.getLogger("onrecord.review")       #a loggerwith a name


#fetches the human-review queue of records, returns ReviewItem format
@router.get("/review", response_model=List[ReviewItem])
def get_review_queue(db: Session = Depends(get_db)) -> List[ReviewItem]:
    #queries for all documents/receipts whose status is pending_review, FIFO 
    docs = db.query(Document).filter(Document.status == "pending_review").order_by(Document.created_at.asc()).all()
    items: List[ReviewItem] = []    #empty list of items

    for doc in docs:    #for every document
        try:    #extracts InvoiceSchema from json string
            extraction = InvoiceSchema.model_validate_json(doc.extracted_json)
        except Exception:
            logger.warning("doc %s has an incompatible extraction schema, skipping", doc.id)
            continue

        #gets pending flagged rowns
        flagged_rows = db.query(ReviewQueueItem).filter(ReviewQueueItem.doc_id == doc.id, ReviewQueueItem.status == "pending").all()
        
        #collection/list of ReviewItem per document
        items.append(
            ReviewItem(
                doc_id=doc.id,
                filename=doc.filename,
                created_at=doc.created_at,
                extraction=extraction,
                flagged_fields=[FlaggedField(field_path=r.field_path, value=r.value, confidence=r.confidence, reason=r.reason or "") for r in flagged_rows],
                watermarked_image_url=f"/image/{doc.id}",
            )
        )
    return items #returns the list of ReviewItem



#helper, correction of data
def _apply_correction(data: dict, field_path: str, corrected: str) -> bool:
    if field_path.startswith("line_items["):
        idx = int(field_path.split("[")[1].rstrip("]"))     #gets index
        if 0 <= idx < len(data.get("line_items", [])):
            #human corrected it, confidence 1.0
            data["line_items"][idx]["description"] = corrected
            data["line_items"][idx]["confidence"] = 1.0 
            return True
        return False

    #if it is not a dictionary, return false
    node = data.get(field_path)
    if not isinstance(node, dict):
        return False

    #converts string to float (if value if numeric int/float)
    if isinstance(node.get("value"), (int, float)):
        try:
            node["value"] = float(corrected)
        except ValueError:
            return False
    else:
        node["value"] = corrected

    node["confidence"] = 1.0 
    return True


#Post a review through approval
@router.post("/approve", response_model=ApproveResponse)
def approve_document(req: ApproveRequest, db: Session = Depends(get_db)) -> ApproveResponse:
    #Gets the document
    doc = db.query(Document).filter(Document.id == req.doc_id).first()
    if not doc:     #if doc is not there
        raise HTTPException(404, detail="Document not found")
    if doc.status not in ("pending_review", "auto_approved"):       #if already reviewed
        raise HTTPException(409, detail=f"Document is in state '{doc.status}'")
    
    #original extraction, applies corrections
    data = json.loads(doc.extracted_json)
    applied = 0
    for corr in req.corrections:
        if _apply_correction(data, corr.field_path, corr.corrected_value):
            applied += 1
            #corrected, human value replaced old one
            row = db.query(ReviewQueueItem).filter(ReviewQueueItem.doc_id == req.doc_id, ReviewQueueItem.field_path == corr.field_path).first()
            if row:
                row.status = "corrected"
                row.corrected_value = corr.corrected_value

    #remaining field items get approved
    db.query(ReviewQueueItem).filter(ReviewQueueItem.doc_id == req.doc_id, ReviewQueueItem.status == "pending").update({"status": "approved"})

    #status change and metrics
    was_pending = doc.status == "pending_review"
    doc.reviewed_json = json.dumps(data)
    doc.status = "approved"
    db.commit()
    if was_pending:     #gauge metric for review items
        metrics.PENDING_REVIEW_GAUGE.dec()
    metrics.REVIEWS_COMPLETED.inc()

    #logs info and returns ApproveResponse
    logger.info("doc %s approved with %d corrections", req.doc_id, applied)
    return ApproveResponse(doc_id=req.doc_id, status="approved", applied_corrections=applied)


#when receipt is rejected in human review stage
@router.post("/reject", response_model=RejectResponse)
def reject_document(req: RejectRequest, db: Session = Depends(get_db)) -> RejectResponse:
    #gets documents
    doc = db.query(Document).filter(Document.id == req.doc_id).first()
    if not doc:     #if doc does not exist
        raise HTTPException(404, detail="Document not found")
    if doc.status not in ("pending_review", "auto_approved"):       #if doc already reviewed previously
        raise HTTPException(409, detail=f"Document is in state '{doc.status}'")

    #status change and metrics + reason
    was_pending = doc.status == "pending_review"
    doc.status = "rejected"
    doc.blocked_reason = req.reason or "Rejected by reviewer"
    db.query(ReviewQueueItem).filter(ReviewQueueItem.doc_id == req.doc_id, ReviewQueueItem.status == "pending").update({"status": "rejected"})
    db.commit()
    #metrics, gauge to change review number
    if was_pending:
        metrics.PENDING_REVIEW_GAUGE.dec()
    logger.info("doc %s rejected: %s", req.doc_id, doc.blocked_reason)
    return RejectResponse(doc_id=req.doc_id, status="rejected")




#document list, Records
@router.get("/documents", response_model=List[DocumentSummary])
def list_documents(limit: int = 50, db: Session = Depends(get_db)) -> List[DocumentSummary]:
    #gets all documents, newest first, readin glimit at 50
    docs = db.query(Document).order_by(Document.created_at.desc()).limit(limit).all()
    out: List[DocumentSummary] = []     #empty list
    for d in docs:      #each doc
        #Sets variables
        vendor = total = currency = None
        extraction = None
        source = d.reviewed_json or d.extracted_json
        #extracted content 
        if source:
            data = json.loads(source)
            vendor = data.get("vendor", {}).get("value")
            total = data.get("total", {}).get("value")
            currency = data.get("currency", {}).get("value")
            try:    #for records with older schemas
                extraction = InvoiceSchema(**data)
            except Exception:
                extraction = None  #for older record

        #appends the documents in the list out and returns it after the loop ends
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



#To get the watermarked image
@router.get("/image/{doc_id}")
def get_image(doc_id: str, db: Session = Depends(get_db)) -> Response:
    #get documents
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc or not doc.image_path:   #doc not there or image not there
        raise HTTPException(404, detail="Image not found")
    
    storage = get_storage()     #storage type, local/s3

    if not storage.exists(doc.image_path):      #image not in storage
        raise HTTPException(404, detail="Image file missing from storage")
    
    return Response(content=storage.load(doc.image_path), media_type="image/png")   #returns image

