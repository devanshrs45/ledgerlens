from __future__ import annotations
import base64
from dataclasses import dataclass
from typing import List, Tuple
from app.config import settings
from app.schemas import FlaggedField, InvoiceSchema
from openai import OpenAI
import json


EXTRACTION_PROMPT = (
    "You are an expert document-intelligence system. Extract structured data "
    "from this receipt or invoice image.\n\n"
    "Rules:\n"
    "- Fill every field of the schema. Use empty string / 0 when a field is "
    "genuinely absent from the document, with a LOW confidence score.\n"
    "- Dates must be ISO format YYYY-MM-DD.\n"
    "- Currency must be an ISO 4217 code (infer from symbols: ₹->INR, $->USD, "
    "€->EUR, £->GBP).\n"
    "- confidence reflects how certain you are of THAT specific value given "
    "image quality, ambiguity, and legibility. Be honest: blurry or partially "
    "occluded values must score low. Never invent a line item — if you are "
    "unsure a line exists, include it with confidence below 0.5 rather than "
    "guessing confidently.\n"
    "- If this image is NOT a receipt or invoice, set every field to empty/0 " 
    "with confidence 0.0 and overall_confidence 0.0.\n"
    "- additional_charges is the SUM of every charge beyond subtotal and tax: "
    "shipping, delivery, tips, service charges, bottle deposits, environment "
    "fees, surcharges. discount is the SUM of every deduction. Use 0 only when "
    "genuinely absent.\n"
    "- The document must reconcile: subtotal + tax + additional_charges "
    "- discount = total. If your values do not satisfy this, re-read the "
    "document before answering.\n"
)

@dataclass
class ExtractionResult:
    invoice: InvoiceSchema
    input_tokens: int
    output_tokens: int
    cost_usd: float


def _client():
    kwargs = {"api_key": settings.OPENAI_API_KEY}
    if settings.OPENAI_BASE_URL:
        kwargs["base_url"] = settings.OPENAI_BASE_URL
    return OpenAI(**kwargs)


def _messages(b64: str, mime: str, extra: str = "") -> list:
    return [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"},
                }, 
                {"type": "text", "text": EXTRACTION_PROMPT + extra},
            ],
        }
    ]


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    return text.strip()


def extract_invoice(image_bytes: bytes, mime: str = "image/png") -> ExtractionResult:
    b64 = base64.standard_b64encode(image_bytes).decode()
    client = _client()

    if settings.STRUCTURED_OUTPUT_MODE == "json":

        schema_hint = (
            "\n\nRespond with ONLY a JSON object (no prose, no markdown fences) "
            "matching exactly this JSON schema:\n"
            + json.dumps(InvoiceSchema.model_json_schema())
        )
        completion = client.chat.completions.create(
            model=settings.VISION_MODEL,
            messages=_messages(b64, mime, schema_hint),
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=2500,
            reasoning_effort="none"
        )
        raw = _strip_fences(completion.choices[0].message.content or "{}")
        invoice = InvoiceSchema.model_validate_json(raw)
    else:
        completion = client.beta.chat.completions.parse(
            model=settings.VISION_MODEL,
            messages=_messages(b64, mime),
            response_format=InvoiceSchema,
        )
        invoice = completion.choices[0].message.parsed

    usage = completion.usage
    input_tokens = getattr(usage, "prompt_tokens", 0) or 0
    output_tokens = getattr(usage, "completion_tokens", 0) or 0
    cost = (
        input_tokens * settings.COST_PER_INPUT_TOKEN
        + output_tokens * settings.COST_PER_OUTPUT_TOKEN
    )
    return ExtractionResult(
        invoice=invoice,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=round(cost, 6),
    )


SCALAR_FIELDS = (
    "vendor",
    "invoice_number",
    "date",
    "currency",
    "subtotal",
    "tax",
    "discount",
    "additional_charges",
    "total",
)


def route_by_confidence(
    invoice: InvoiceSchema, threshold: float | None = None
) -> Tuple[str, List[FlaggedField]]:
    
    threshold = settings.REVIEW_THRESHOLD if threshold is None else threshold
    flagged: List[FlaggedField] = []

    for name in SCALAR_FIELDS:
        node = getattr(invoice, name)
        if node.confidence < threshold:
            flagged.append(
                FlaggedField(
                    field_path=name,
                    value=str(node.value),
                    confidence=node.confidence,
                )
            )

    for i, item in enumerate(invoice.line_items):
        if item.confidence < threshold:
            flagged.append(
                FlaggedField(
                    field_path=f"line_items[{i}]",
                    value=(
                        f"{item.description} x{item.quantity} "
                        f"@ {item.unit_price} = {item.amount}"
                    ),
                    confidence=item.confidence,
                )
            )

    flagged.extend(sanity_flags(invoice))
    status = "auto_approved" if not flagged else "pending_review"
    return status, flagged


def sanity_flags(invoice: InvoiceSchema) -> List[FlaggedField]:
    flags: List[FlaggedField] = []

    if not invoice.vendor.value.strip():
        flags.append(FlaggedField(field_path="vendor", value="", confidence=0.0))

    if invoice.total.value <= 0:
        flags.append(FlaggedField(
            field_path="total", value=str(invoice.total.value), confidence=0.0))

    if not invoice.line_items:
        flags.append(FlaggedField(
            field_path="line_items", value="none extracted", confidence=0.0))

    if invoice.total.value > 0:
        base = invoice.subtotal.value + invoice.tax.value + invoice.additional_charges.value
        if (abs(base - invoice.total.value) > 0.02
                and abs(base - invoice.discount.value - invoice.total.value) > 0.02):
            flags.append(FlaggedField(
                field_path="total",
                value=str(invoice.total.value),
                confidence=0.0,
            ))

    return flags