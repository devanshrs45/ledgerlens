from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Float, ForeignKey, LargeBinary, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

_db_url = settings.DATABASE_URL
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql+psycopg://", 1)
elif _db_url.startswith("postgresql://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+psycopg://", 1)
connect_args = {"check_same_thread": False} if _db_url.startswith("sqlite") else {}
engine = create_engine(_db_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Document(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True)
    filename = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending_review")
    extracted_json = Column(Text, nullable=True)
    reviewed_json = Column(Text, nullable=True)
    image_path = Column(String, nullable=True)
    blocked_reason = Column(String, nullable=True)
    cost_usd = Column(Float, default=0.0)
    created_at = Column(DateTime, default=utcnow)


class ReviewQueueItem(Base):
    __tablename__ = "review_queue"
    id = Column(String, primary_key=True)
    doc_id = Column(String, ForeignKey("documents.id"), nullable=False)
    field_path = Column(String, nullable=False)
    value = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False)
    status = Column(String, nullable=False, default="pending") # pending | corrected | approved
    corrected_value = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class ImageBlob(Base):
    __tablename__ = "image_blobs"
    key = Column(String, primary_key=True) # "{doc_id}/{filename}"
    data = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime, default=utcnow)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

