import io
import importlib
import pytest
from PIL import Image
from app import storage
from app.routers import ingest as ingest_router
from app.routers import review as review_router
from app import extraction
from app.schemas import InvoiceSchema


@pytest.fixture()
def client(monkeypatch, tmp_path, valid_invoice_dict):
    monkeypatch.setenv("MODERATION_SET", "false")
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("DATABASE_URL", "sqlite://")

    from app import config
    importlib.reload(config)
    from app import database
    importlib.reload(database)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    database.engine = engine
    database.SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    database.Base.metadata.create_all(bind=engine)

    importlib.reload(storage)
    importlib.reload(ingest_router)
    importlib.reload(review_router)

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

    from app import main
    importlib.reload(main)
    from fastapi.testclient import TestClient

    database.Base.metadata.create_all(bind=database.engine)

    c = TestClient(main.app)
    c._state = state          
    c._modules = (ingest_router, review_router, database)
    return c


def _png():
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (210, 190, 170)).save(buf, format="PNG")
    return buf.getvalue()


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_metrics_exposed(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "extraction_latency_seconds" in r.text
    assert "token_cost_usd" in r.text


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

    assert client.get("/review").json() == []

    docs = client.get("/documents").json()
    doc = next(d for d in docs if d["doc_id"] == doc_id)
    assert doc["status"] == "approved"
    assert doc["vendor"] == "Fixed Shop"


def test_approve_missing_doc_404(client):
    r = client.post("/approve", json={"doc_id": "nope", "corrections": []})
    assert r.status_code == 404


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



def test_cannot_approve_after_reject(client, valid_invoice_dict):
    client._state["invoice_dict"] = valid_invoice_dict(total_conf=0.20)
    ingest = client.post("/ingest", files={"file": ("r.png", _png(), "image/png")})
    doc_id = ingest.json()["doc_id"]

    client.post("/reject", json={"doc_id": doc_id, "reason": "x"})
    r = client.post("/approve", json={"doc_id": doc_id, "corrections": []})
    assert r.status_code == 409



def test_documents_lists_all(client):
    client.post("/ingest", files={"file": ("a.png", _png(), "image/png")})
    client.post("/ingest", files={"file": ("b.png", _png(), "image/png")})
    docs = client.get("/documents").json()
    assert len(docs) == 2



def test_blocked_upload_returns_422_and_skips_extraction(client, monkeypatch):
    ingest_router, _, _ = client._modules
    from app.moderation import ModerationVerdict
    monkeypatch.setattr(
        ingest_router, "moderate_image",
        lambda raw, image_type="image/png": ModerationVerdict(
            allowed=False, blocked_reason="unsafe content"),
    )
    
    def _boom(*a, **k):
        raise AssertionError("extraction ran on a blocked upload")
    monkeypatch.setattr(ingest_router, "extract_invoice", _boom)

    r = client.post("/ingest", files={"file": ("r.png", _png(), "image/png")})
    assert r.status_code == 422
    assert "blocked_reason" in r.json()["detail"]
