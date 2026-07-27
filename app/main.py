'''
main.py -> Sets up application:
- Sets up logging, FastAPI startup/shutdown
- Instantiates the application, Middleware to wrap all requests
- Registers routers (ingest, review)
- Health checkup, Metrics endpoint
- Frontend link to HTML, CSS, JS
'''

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from app.database import init_db
from app.routers import ingest, review

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")    #sets up root logger

#code startuo/shutdown throguh FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    #before yield, startup
    init_db()
    yield
    #after yield, shutdown, nothing

#Instantiates the application
app = FastAPI(
    title="OnRecord",
    description="Drop in photoes of any receipt or invoice; get schema-validated structured data, per-field confidence scores, and a review queue for the rows the model isn't sure about.",
    version="1.0.0",
    lifespan=lifespan,
)

#wraps every request through app
app.add_middleware(
    CORSMiddleware,     #CORS
    allow_origins=["*"],    #any website can call this api
    allow_methods=["*"],    #any HTTP
    allow_headers=["*"],    #any request headers
)

#routers, ingest and review
app.include_router(ingest.router, tags=["ingest"])
app.include_router(review.router, tags=["review"])

#Health checkup
@app.get("/health", tags=["ops"])
def health() -> dict:
    return {"status": "ok", "service": "onrecord"}

#metrics endpoint, all prometheus metrics used
@app.get("/metrics", tags=["ops"])
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


#Frontent link, links to index.html, and eventually styles.css and app.js
app.mount("/", StaticFiles(directory="static", html=True), name="ui")