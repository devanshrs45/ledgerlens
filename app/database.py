'''
database.py -> Persistence layer:
- For AWS/Local storage
- Rewrites URL from RDS
- Document and Review Table format
- Creates blank table initially
- Creates new session for each request
'''

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Float, ForeignKey, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings


_db_url = settings.DATABASE_URL     #db url

#rewriting url from RDS to recognisable format by SQLAlchemy
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql+psycopg://", 1)
elif _db_url.startswith("postgresql://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+psycopg://", 1)
connect_args = {"check_same_thread": False} if _db_url.startswith("sqlite") else {}
engine = create_engine(_db_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

#hekper function to get utc time
def utcnow() -> datetime:
    return datetime.now(timezone.utc)

#Main record
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

#one row of flagged fields
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
    reason = Column(Text, nullable=True)


#creates all empty tables
def init_db() -> None:
    Base.metadata.create_all(bind=engine)

#new session for each request
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

