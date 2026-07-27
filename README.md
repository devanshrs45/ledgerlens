# OnRecord

**Receipts in. Records out.**

A document intelligence service that turns a photo of a receipt or invoice into
validated, structured data with per-field confidence scores. Anything the model
is unsure about is routed to a human review queue instead of being silently
trusted.

Built as Capstone C-02, LedgerLens.

---

## What it does

1. You upload a receipt or invoice image (single file or a batch).
2. The image passes a safety gate, then goes to a vision model for extraction.
3. The result is validated against a strict Pydantic schema.
4. Every field carries a confidence score. Fields below `0.75` are flagged.
5. Independently of confidence, deterministic rules check the arithmetic
   (does `subtotal + tax + charges - discount` actually equal `total`?) and
   catch empty vendors, zero totals, and missing line items.
6. Clean documents are auto-approved. Anything flagged goes to a review queue
   where a human can correct the values and approve, or reject the document.
7. A watermarked copy of the image (document ID + UTC timestamp) is stored, and
   the record is saved with a full audit trail.

---

## Tech stack

| Layer | Choice |
|---|---|
| API | FastAPI |
| Validation | Pydantic v2 |
| Vision model | Qwen (`qwen/qwen3.6-27b`) via Groq, using the OpenAI SDK |
| Database | SQLAlchemy — SQLite locally, PostgreSQL (RDS) in the cloud |
| Image handling | Pillow (resize + watermark) |
| Storage | Local filesystem or Amazon S3 (swappable backend) |
| Metrics | Prometheus client, exposed at `/metrics` |
| Frontend | Single-file HTML/CSS/JS, served by FastAPI |
| Tests | pytest (90 tests) |
| Deployment | Docker image on Amazon ECS Express Mode |

---

## Running it locally

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Create a `.env` file

```env
OPENAI_API_KEY=gsk_your_groq_key_here
OPENAI_BASE_URL=https://api.groq.com/openai/v1
VISION_MODEL=qwen/qwen3.6-27b
OUTPUT_FORMAT=json

MODERATION_SET=false
REVIEW_THRESHOLD=0.75

IMAGE_DIM=1024
STORAGE_BACKEND=local
UPLOAD_DIR=uploads

DATABASE_URL=sqlite:///./onrecord.db
```

> The key is named `OPENAI_API_KEY` because the app uses the OpenAI SDK pointed
> at Groq's compatible endpoint. Put your Groq `gsk_...` key there.

### 3. Run

```bash
uvicorn app.main:app --reload --port 8000
```

Then open **http://localhost:8000** for the UI, or
**http://localhost:8000/docs** for the API documentation.

---

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | — | Groq API key (required) |
| `OPENAI_BASE_URL` | Groq endpoint | Where extraction calls go |
| `VISION_MODEL` | `qwen/qwen3.6-27b` | Vision model used for extraction |
| `OUTPUT_FORMAT` | `json` | JSON mode + Pydantic validation |
| `MODERATION_SET` | `false` | Turns the safety gate on/off |
| `MODERATION_API_KEY` | — | OpenAI key, only needed if the gate is on |
| `REVIEW_THRESHOLD` | `0.75` | Below this confidence, a field is flagged |
| `IMAGE_DIM` | `1024` | Images are downscaled to this before extraction |
| `STORAGE_BACKEND` | `local` | `local` or `s3` |
| `S3_BUCKET` | — | Bucket name when using S3 |
| `AWS_REGION` | `ap-south-1` | Region for S3 |
| `DATABASE_URL` | SQLite file | SQLite locally, PostgreSQL in the cloud |

---

## API

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/ingest` | Upload an image, get structured data back |
| `GET` | `/review` | List documents waiting for human review |
| `POST` | `/approve` | Approve a document, optionally with corrections |
| `POST` | `/reject` | Reject a document with a reason |
| `GET` | `/documents` | List all processed documents |
| `GET` | `/image/{doc_id}` | Fetch the watermarked image |
| `GET` | `/health` | Health check |
| `GET` | `/metrics` | Prometheus metrics |

---

## Tests

90 tests, all passing, no network or API keys required — external services are
mocked and the database runs in memory.

```bash
pip install pytest httpx
pytest -q
```

| File | Covers |
|---|---|
| `test_schema_contracts.py` | JSON round-trip, field presence, confidence bounds |
| `test_confidence_router.py` | Threshold routing and the deterministic rule checks |
| `test_pii.py` | Redaction patterns and their guards |
| `test_moderation.py` | Safety gate on, off, and misconfigured |
| `test_watermark_storage.py` | Watermarking, resizing, storage round-trip |
| `test_database.py` | Connection URL rewriting, model columns |
| `test_api_pipeline.py` | Full HTTP flow end to end |

---

## Deployment

Deployed on AWS using:

- **Amazon S3** — watermarked image storage
- **Amazon RDS (PostgreSQL)** — documents and review queue
- **Amazon ECR** — container image registry
- **Amazon ECS Express Mode** — runs the container on Fargate behind an HTTPS
  load balancer

Full step-by-step instructions are in
`OnRecord_AWS_ECS_Deployment_Guide.pdf`.

The short version: build the Docker image, push it to ECR, then point an ECS
Express Mode service at it with the environment variables above (using
`STORAGE_BACKEND=s3` and the RDS connection string).

---

## Project structure

```
onrecord/
├── app/
│   ├── main.py            FastAPI app, routers, /health, /metrics
│   ├── config.py          Settings loaded from environment
│   ├── schemas.py         Pydantic models (InvoiceSchema and friends)
│   ├── extraction.py      Vision model call, confidence routing, rule checks
│   ├── moderation.py      Safety gate
│   ├── watermark.py       Image resize and watermarking
│   ├── storage.py         Local / S3 storage backends
│   ├── database.py        SQLAlchemy models and session handling
│   ├── pii.py             Redaction applied before logging
│   ├── metrics.py         Prometheus metrics
│   └── routers/
│       ├── ingest.py      POST /ingest
│       └── review.py      /review, /approve, /reject, /documents, /image
├── static/
│   └── index.html         The entire HTML
    └── app.js             The entire JS
    └── styles.css         The entire CSS
├── tests/                 pytest suite
├── Dockerfile
└── requirements.txt
```

---

## Design notes

**Confidence alone is not trusted.** A vision model will happily return empty
values with `0.99` confidence when shown something that isn't a receipt. The
deterministic rule checks in `extraction.py` run independently of the model's
self-reported confidence and catch exactly this case.

**Two interpretations of discount are accepted.** Receipts are inconsistent
about whether the printed total already has the discount subtracted. The
reconciliation check passes if either reading balances, which avoids a large
class of false flags.

**Audit trail is preserved.** The original model output stays in
`extracted_json`; human corrections are written separately to `reviewed_json`.
Nothing is overwritten.

**PII is redacted before logging.** Emails, phone numbers, cards, and Indian
identifiers (Aadhaar with a Verhoeff checksum, PAN, GSTIN) are stripped from
log lines. Redaction applies to logs only, never to stored records.

**Storage is swappable.** The same code writes to a local folder or to S3
depending on one environment variable, which is what lets the app run
identically on a laptop and in the cloud.

---

## Known limitations

- The moderation gate ships disabled (`MODERATION_SET=false`). The code and its
  tests are complete; it can be enabled with one environment variable plus a key.
- Model-reported confidence is not calibrated. The deterministic checks exist
  precisely because of this.
- Line item corrections in the review UI edit the description only.
- Throughput metrics are per-process and reset on restart.
- There is no database migration path — schema changes require recreating the
  tables.
