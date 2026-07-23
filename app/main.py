import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from app.database import init_db
from app.routers import ingest, review

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="LedgerLens",
    description=(
        "Drop in a photo of any receipt or invoice; get schema-validated "
        "structured data, per-field confidence scores, and a review queue "
        "for the rows the model isn't sure about."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router, tags=["ingest"])
app.include_router(review.router, tags=["review"])


@app.get("/health", tags=["ops"])
def health() -> dict:
    return {"status": "ok", "service": "ledgerlens"}


@app.get("/metrics", tags=["ops"])
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

app.mount("/", StaticFiles(directory="static", html=True), name="ui")