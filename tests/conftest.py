import os
import io
import importlib
import pytest

os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("VISION_MODEL", "qwen/qwen3.6-27b")
os.environ.setdefault("OUTPUT_FORMAT", "json")
os.environ.setdefault("MODERATION_SET", "false")
os.environ.setdefault("REVIEW_THRESHOLD", "0.75")
os.environ.setdefault("MODERATION_THRESHOLD", "0.5")
os.environ.setdefault("IMAGE_DIM", "1024")
os.environ.setdefault("STORAGE_BACKEND", "local")
os.environ.setdefault("DATABASE_URL", "sqlite://")


@pytest.fixture()
def settings():
    from app import config
    importlib.reload(config)
    return config.settings


@pytest.fixture()
def tiny_png_bytes():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (200, 180, 160)).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture()
def big_png_bytes():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (3000, 2000), (120, 120, 120)).save(buf, format="PNG")
    return buf.getvalue()


def make_confident(value, confidence):
    return {"value": value, "confidence": confidence}


@pytest.fixture()
def valid_invoice_dict():
    def _make(**over):
        base = {
            "vendor": make_confident(over.get("vendor", "Corner Shop"),
                                     over.get("vendor_conf", 0.95)),
            "invoice_number": make_confident(over.get("invoice_number", "INV-001"),
                                             over.get("invoice_number_conf", 0.95)),
            "date": make_confident(over.get("date", "2026-07-12"),
                                   over.get("date_conf", 0.95)),
            "currency": make_confident(over.get("currency", "INR"),
                                       over.get("currency_conf", 0.95)),
            "subtotal": make_confident(over.get("subtotal", 100.0),
                                       over.get("subtotal_conf", 0.95)),
            "tax": make_confident(over.get("tax", 10.0),
                                  over.get("tax_conf", 0.95)),
            "discount": make_confident(over.get("discount", 0.0),
                                       over.get("discount_conf", 0.95)),
            "additional_charges": make_confident(over.get("additional_charges", 0.0),
                                                 over.get("additional_charges_conf", 0.95)),
            "total": make_confident(over.get("total", 110.0),
                                    over.get("total_conf", 0.95)),
            "line_items": over.get("line_items", [
                {"description": "Bread and milk", "quantity": 1.0,
                 "unit_price": 100.0, "amount": 100.0, "confidence": 0.95},
            ]),
            "overall_confidence": over.get("overall_confidence", 0.95),
        }
        return base
    return _make


@pytest.fixture()
def db_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app import database

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    database.Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
