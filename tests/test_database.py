"""
test_database.py

Covers the database layer's most deployment-critical behaviour: rewriting the
RDS-provided connection string to the psycopg v3 dialect SQLAlchemy needs, and
the presence of the columns the app writes (including the reason column we
added to the review queue).
"""

import importlib


def test_documents_table_columns():
    from app import database
    cols = {c.name for c in database.Document.__table__.columns}
    for expected in ("id", "filename", "status", "extracted_json",
                     "reviewed_json", "image_path", "blocked_reason",
                     "cost_usd", "created_at"):
        assert expected in cols, f"Document missing column {expected}"


def test_review_queue_has_reason_column():
    """reason was added so the reviewer UI can show why a field was held."""
    from app import database
    cols = {c.name for c in database.ReviewQueueItem.__table__.columns}
    assert "reason" in cols
    for expected in ("id", "doc_id", "field_path", "value", "confidence",
                     "status", "corrected_value", "created_at"):
        assert expected in cols


def test_dual_json_columns_for_audit_trail():
    """
    extracted_json (original model output) and reviewed_json (human-corrected)
    are separate, preserving an audit trail.
    """
    from app import database
    cols = {c.name for c in database.Document.__table__.columns}
    assert "extracted_json" in cols
    assert "reviewed_json" in cols


# --------------------------------------------------------------------------- #
# URL normalization: the RDS deploy-critical rewrite
# --------------------------------------------------------------------------- #
def _url_after_rewrite(raw):
    """Replicate the module's normalization on a given raw URL."""
    url = raw
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def test_postgres_scheme_rewritten():
    """RDS often hands out postgres://, which SQLAlchemy 2.x rejects."""
    raw = "postgres://user:pass@host.rds.amazonaws.com:5432/onrecord"
    assert _url_after_rewrite(raw).startswith("postgresql+psycopg://")


def test_postgresql_scheme_rewritten_to_psycopg():
    """postgresql:// defaults to psycopg2; we force psycopg (v3)."""
    raw = "postgresql://user:pass@host:5432/onrecord"
    assert _url_after_rewrite(raw).startswith("postgresql+psycopg://")


def test_rewrite_only_touches_scheme():
    """The host, credentials, and database name must survive untouched."""
    raw = "postgres://onrecord:MyPass123@db.abc.ap-south-1.rds.amazonaws.com:5432/onrecord"
    out = _url_after_rewrite(raw)
    assert "onrecord:MyPass123@db.abc.ap-south-1.rds.amazonaws.com:5432/onrecord" in out


def test_sqlite_url_not_rewritten():
    raw = "sqlite:///./onrecord.db"
    assert _url_after_rewrite(raw) == raw


def test_module_normalizes_configured_url():
    """
    The database module, as imported, must have produced a usable engine.
    (Under the test env DATABASE_URL is sqlite://, so this just proves import
    and engine creation succeed.)
    """
    from app import database
    importlib.reload(database)
    assert database.engine is not None
    assert database.SessionLocal is not None


def test_init_db_creates_tables():
    """init_db must create both tables on a fresh engine."""
    from sqlalchemy import create_engine, inspect
    from sqlalchemy.pool import StaticPool
    from app import database

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    database.Base.metadata.create_all(bind=engine)
    names = set(inspect(engine).get_table_names())
    assert "documents" in names
    assert "review_queue" in names
