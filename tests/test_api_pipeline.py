"""
test_api_pipeline.py

End-to-end tests of the HTTP surface using FastAPI's TestClient. Extraction is
mocked (no Groq call), the database is swapped for in-memory SQLite, and
storage writes to a temp dir. This exercises the real routers, the moderation
ordering, metric updates, and the approve/reject state machine.

This is the closest thing to the brief's "test_api_pipeline" idea: prove the
whole request path works without any external dependency.
"""

import io
import importlib
import pytest
from PIL import Image


@pytest.fixture()
def client(monkeypatch, tmp_path, valid_invoice_dict):
    """
    Build a TestClient with:
    - in-memory SQLite (shared via StaticPool)
    - storage pointed at a temp directory
    - moderation forced OFF
    - extract_invoice monkeypatched to return a canned result (no Groq)
    """
    monkeypatch.setenv("MODERATION_SET", "false")
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("DATABASE_URL", "sqlite://")

    # Reload modules so they pick up the env above.
    from app import config
    importlib.reload(config)
    from app import database
    importlib.reload(database)

    # Point the app's engine/session at a shared in-memory DB.
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    database.engine = engine
    database.SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    database.Base.metadata.create_all(bind=engine)

    # Reload storage + routers so they see the reloaded config/db.
    from app import storage
    importlib.reload(storage)
    from app.routers import ingest as ingest_router
    importlib.reload(ingest_router)
    from app.routers import review as review_router
    importlib.reload(review_router)

    # Mock extraction: return an ExtractionOutput-like object.
    from app import extraction
    from app.schemas import InvoiceSchema

    class _Canned:
        def __init__(self, invoice, cost=0.00123):
            self.invoice = invoice
            self.input_tokens = 100
            self.output_tokens = 50
            self.cost_usd = cost

    state = {"invoice_dict": valid_invoice_dict()}

    def fake_extract(image_bytes, image_type="image/png"):
        inv = InvoiceSchema.model_validate(state["invoice_dict"])
        return _Canned(inv)

    monkeypatch.setattr(ingest_router, "extract_invoice", fake_extract)

    # Build the app fresh so it wires the reloaded routers.
    from app import main
    importlib.reload(main)
    from fastapi.testclient import TestClient

    # Ensure tables exist on the app's engine (init_db uses database.engine).
    database.Base.metadata.create_all(bind=database.engine)

    c = TestClient(main.app)
    c._state = state          # let tests tweak the canned extraction
    c._modules = (ingest_router, review_router, database)
    return c


def _png():
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (210, 190, 170)).save(buf, format="PNG")
    return buf.getvalue()


# --------------------------------------------------------------------------- #
# Ops endpoints
# --------------------------------------------------------------------------- #
def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_metrics_exposed(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    # Prometheus exposition mentions our metric names.
    assert "extraction_latency_seconds" in r.text
    assert "token_cost_usd" in r.text


# --------------------------------------------------------------------------- #
# Ingest -> auto-approve
# --------------------------------------------------------------------------- #
def test_ingest_auto_approve(client):
    r = client.post("/ingest", files={"file": ("r.png", _png(), "image/png")})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "auto_approved"
    assert body["doc_id"]
    assert body["watermarked_image_url"].startswith("/image/")


def test_ingest_rejects_non_image(client):
    r = client.post("/ingest", files={"file": ("r.txt", b"hello", "text/plain")})
    assert r.status_code == 415


def test_ingest_rejects_empty(client):
    r = client.post("/ingest", files={"file": ("r.png", b"", "image/png")})
    assert r.status_code == 400


# --------------------------------------------------------------------------- #
# Ingest -> pending review (low confidence)
# --------------------------------------------------------------------------- #
def test_ingest_pending_review(client, valid_invoice_dict):
    client._state["invoice_dict"] = valid_invoice_dict(total_conf=0.30)
    r = client.post("/ingest", files={"file": ("r.png", _png(), "image/png")})
    assert r.status_code == 200
    assert r.json()["status"] == "pending_review"
    assert len(r.json()["flagged_fields"]) >= 1


def test_review_queue_lists_pending(client, valid_invoice_dict):
    client._state["invoice_dict"] = valid_invoice_dict(vendor_conf=0.20)
    client.post("/ingest", files={"file": ("r.png", _png(), "image/png")})
    r = client.get("/review")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["flagged_fields"]


# --------------------------------------------------------------------------- #
# Approve with corrections -> writes reviewed_json, moves to approved
# --------------------------------------------------------------------------- #
def test_approve_with_correction(client, valid_invoice_dict):
    client._state["invoice_dict"] = valid_invoice_dict(vendor="", vendor_conf=0.20)
    ingest = client.post("/ingest", files={"file": ("r.png", _png(), "image/png")})
    doc_id = ingest.json()["doc_id"]

    r = client.post("/approve", json={
        "doc_id": doc_id,
        "corrections": [{"field_path": "vendor", "corrected_value": "Fixed Shop"}],
    })
    assert r.status_code == 200
    assert r.json()["status"] == "approved"
    assert r.json()["applied_corrections"] == 1

    # It should no longer be in the review queue.
    assert client.get("/review").json() == []

    # And it shows in documents with the corrected vendor.
    docs = client.get("/documents").json()
    doc = next(d for d in docs if d["doc_id"] == doc_id)
    assert doc["status"] == "approved"
    assert doc["vendor"] == "Fixed Shop"


def test_approve_missing_doc_404(client):
    r = client.post("/approve", json={"doc_id": "nope", "corrections": []})
    assert r.status_code == 404


# --------------------------------------------------------------------------- #
# Reject -> rejected status
# --------------------------------------------------------------------------- #
def test_reject(client, valid_invoice_dict):
    client._state["invoice_dict"] = valid_invoice_dict(total_conf=0.20)
    ingest = client.post("/ingest", files={"file": ("r.png", _png(), "image/png")})
    doc_id = ingest.json()["doc_id"]

    r = client.post("/reject", json={"doc_id": doc_id, "reason": "Not a receipt"})
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"

    docs = client.get("/documents").json()
    doc = next(d for d in docs if d["doc_id"] == doc_id)
    assert doc["status"] == "rejected"


def test_reject_missing_doc_404(client):
    r = client.post("/reject", json={"doc_id": "nope", "reason": "x"})
    assert r.status_code == 404


# --------------------------------------------------------------------------- #
# 409 state guard: cannot approve an already-rejected document
# --------------------------------------------------------------------------- #
def test_cannot_approve_after_reject(client, valid_invoice_dict):
    client._state["invoice_dict"] = valid_invoice_dict(total_conf=0.20)
    ingest = client.post("/ingest", files={"file": ("r.png", _png(), "image/png")})
    doc_id = ingest.json()["doc_id"]

    client.post("/reject", json={"doc_id": doc_id, "reason": "x"})
    r = client.post("/approve", json={"doc_id": doc_id, "corrections": []})
    assert r.status_code == 409


# --------------------------------------------------------------------------- #
# Documents ledger
# --------------------------------------------------------------------------- #
def test_documents_lists_all(client):
    client.post("/ingest", files={"file": ("a.png", _png(), "image/png")})
    client.post("/ingest", files={"file": ("b.png", _png(), "image/png")})
    docs = client.get("/documents").json()
    assert len(docs) == 2


# --------------------------------------------------------------------------- #
# Moderation ordering: a blocked upload returns 422 and never extracts
# --------------------------------------------------------------------------- #
def test_blocked_upload_returns_422_and_skips_extraction(client, monkeypatch):
    ingest_router, _, _ = client._modules

    # Force the gate to block.
    from app.moderation import ModerationVerdict
    monkeypatch.setattr(
        ingest_router, "moderate_image",
        lambda raw, image_type="image/png": ModerationVerdict(
            allowed=False, blocked_reason="unsafe content"),
    )
    # If extraction is called, fail the test.
    def _boom(*a, **k):
        raise AssertionError("extraction ran on a blocked upload")
    monkeypatch.setattr(ingest_router, "extract_invoice", _boom)

    r = client.post("/ingest", files={"file": ("r.png", _png(), "image/png")})
    assert r.status_code == 422
    assert "blocked_reason" in r.json()["detail"]
