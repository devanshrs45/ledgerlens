'''
extraction.py -> Vision Extraction and Confidence:
- Extraction Prompt + Rules
- OpenAI SDK, Extraction Format, Multimodal message
- base64 encoding, build client, calls Groq using JSON and w/o JSON, calculates total cost, returns output
- Confidence chenck, Auto-approves if none flagged. If flagged, sends for human-review
- Deterministic rule based flags that check the values, example some wierd/impossible values, wrong arithmetic, etc
'''

from __future__ import annotations
import base64
from dataclasses import dataclass
from typing import List, Tuple
from app.config import settings
from app.schemas import FlaggedField, InvoiceSchema
from openai import OpenAI
import json


#instruction block sent to the vision model 
EXTRACTION_PROMPT = (
    "You are an expert document-intelligence system. Extract structured data from this receipt or invoice image.\n\n"

    "Evidence rules:\n"
    "- Only return a value when it is explicitly visible and supported by a printed label.\n"
    "- Never invent or calculate a subtotal, tax, discount, date, invoice number, or charge merely to make the arithmetic balance.\n"
    "- If a value is unclear, obscured, rotated, or not explicitly labelled, return 0 or an empty string with confidence below 0.60.\n"
    "- Confidence measures visible evidence, not whether the result seems plausible.\n"
    "- Do not assign confidence above 0.85 unless both the label and complete value are clearly readable.\n\n"

    "Field rules:\n"
    "- Date must come from a field explicitly labelled Invoice Date, Bill Date, Receipt Date, or Date. Do not use service date, sold date, due date, RO date, payment date, manufacturing date, or watermark date.\n"
    "- Currency must be an ISO 4217 code.\n"
    "- Subtotal must come from a printed Subtotal, Net Amount, Taxable Amount, or equivalent field. Do not derive it from total minus tax.\n"
    "- Tax must be the sum of all explicitly printed tax components such as CGST, SGST, IGST, VAT, or GST.\n"
    "- Discount must be nonzero only when an explicit discount, coupon, rebate, saving, credit, or deduction is printed.\n"
    "- Additional charges must include only explicitly printed fees or charges.\n"
    "- Total must come from the printed Grand Total, Amount Payable, or Total field.\n"
    "- Preserve printed decimal values. Do not replace an exact total with a rounded value unless the document explicitly labels it Rounded Total.\n\n"

    "Validation rules:\n"
    "- Verify subtotal + tax + additional_charges - discount equals total.\n"
    "- If the printed fields do not tally, preserve the printed values and lower overall_confidence. Do not alter one value to force the arithmetic to match.\n"
    "- If this is not a receipt or invoice, return empty or zero values with confidence 0.0.\n"
)

#format of one extraction output
@dataclass
class ExtractionOutput:
    invoice: InvoiceSchema
    input_tokens: int
    output_tokens: int
    cost_usd: float

#builds openai SDK, to use Groq
def _client():
    kwargs = {"api_key": settings.OPENAI_API_KEY}
    if settings.OPENAI_BASE_URL:
        kwargs["base_url"] = settings.OPENAI_BASE_URL
    return OpenAI(**kwargs)


#multimodal chat message format. image, text prompt, schema hint.
def _messages(b64: str, image_type: str, extra: str = "") -> list:
    return [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{image_type};base64,{b64}"}}, 
                {"type": "text", "text": EXTRACTION_PROMPT + extra},
            ],
        }
    ]

#To strip the fences (`) at the start and end if there
def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    return text.strip()


#Main extraction function
def extract_invoice(image_bytes: bytes, image_type: str = "image/png") -> ExtractionOutput:
    b64 = base64.standard_b64encode(image_bytes).decode()   #encodes in base 64
    client = _client()  #builds the client for Groq

    if settings.OUTPUT_FORMAT == "json":        #for JSON output
        schema_hint = (
            "\n\nRespond with ONLY a JSON object (no prose, no markdown fences) matching exactly this JSON schema:\n"
            + json.dumps(InvoiceSchema.model_json_schema())
        )   #injects the actual schema so the model knows the format

        completion = client.chat.completions.create(
            model=settings.VISION_MODEL,
            messages=_messages(b64, image_type, schema_hint),
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=2500,
            reasoning_effort="none"
        )   #calls model
        raw = _strip_fences(completion.choices[0].message.content or "{}")
        invoice = InvoiceSchema.model_validate_json(raw)    #checks json format and validates it

    else:       #without json
        completion = client.beta.chat.completions.parse(
            model=settings.VISION_MODEL,
            messages=_messages(b64, image_type),
            response_format=InvoiceSchema,
        )
        invoice = completion.choices[0].message.parsed

    #cost calculation
    usage = completion.usage    #usage report for tokens ("prompt_tokens", "completion_tokens", "total_tokens")
    input_tokens = getattr(usage, "prompt_tokens", 0) or 0      #input tokens, used prompt_tokens from usage
    output_tokens = getattr(usage, "completion_tokens", 0) or 0     #output tokens, used completion_tokens from usage
    cost = (input_tokens * settings.INPUT_TOKEN_COST) + (output_tokens * settings.OUTPUT_TOKEN_COST)    #computes the total cose
    
    #Returns everything in this format
    return ExtractionOutput(
        invoice=invoice,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=round(cost, 6),
    )

#Extracted value fields
SCALAR_FIELDS = ("vendor", "invoice_number", "date", "currency", "subtotal", "tax", "discount", "additional_charges", "total")

#decides based on confidence scores
def route_by_confidence(invoice: InvoiceSchema, threshold: float | None = None) -> Tuple[str, List[FlaggedField]]:
    #sets threshold (if none) and empty list of flagged fields
    threshold = settings.REVIEW_THRESHOLD if threshold is None else threshold
    flagged: List[FlaggedField] = []

    #checks overall confidence
    if invoice.overall_confidence < threshold:
        flagged.append(
            FlaggedField(
                field_path="overall_confidence",
                value=str(invoice.overall_confidence),
                confidence=invoice.overall_confidence,
                reason=(
                    f"Overall extraction confidence "
                    f"({invoice.overall_confidence:.2f}) is below "
                    f"the {threshold:.2f} review threshold."
                ),
            )
        )

    #iterates through scalar fields and checks confidence
    for name in SCALAR_FIELDS:
        node = getattr(invoice, name)
        if node.confidence < threshold:     #if low confident, appends in flagged as a FlaggedField format
            flagged.append(
                FlaggedField(
                    field_path=name,
                    value=str(node.value),
                    confidence=node.confidence,
                    reason=f"Low confidence ({node.confidence:.2f}) — below the {threshold:.2f} review threshold."
                )
            )

    #for each line item. if confidence is below threshold, flag
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
                    reason=f"Low confidence ({item.confidence:.2f}) on this line item."
                )
            )

    
    flagged.extend(deterministic_rule_based_flags(invoice))   #adds some deterministic checks regardless of confidence
    status = "auto_approved" if not flagged else "pending_review"       #If nothing is flagged, autoapprove. else sent for review
    return status, flagged


#catches what the confidence scores cannot. This inspects the values of the extracted content and check if they make sense
def deterministic_rule_based_flags(invoice: InvoiceSchema) -> List[FlaggedField]:
    flags: List[FlaggedField] = []      #empty list of flagged

    if not invoice.vendor.value.strip():     #if model adds empty vendor name with high confidence
        flags.append(FlaggedField(field_path="vendor", value="", confidence=0.0, reason="Vendor name is empty. Most likely not a valid receipt."))

    if invoice.total.value <= 0:        #if total price is <= 0
        flags.append(FlaggedField(
            field_path="total", value=str(invoice.total.value), confidence=0.0, reason="Total is zero or negative. No payable amount found."))

    if not invoice.line_items:      #if there are no line items
        flags.append(FlaggedField(
            field_path="line_items", value="none extracted", confidence=0.0, reason="No line items were extracted from the document."))

    if invoice.total.value > 0:     #if total > 0, but then the sum of costs is not adding up to total
        base = invoice.subtotal.value + invoice.tax.value + invoice.additional_charges.value     #discrepancy in cost calculation
        if (abs(base - invoice.total.value) > 0.02 and abs(base - invoice.discount.value - invoice.total.value) > 0.02):
            flags.append(FlaggedField(
                field_path="total",
                value=str(invoice.total.value),
                confidence=invoice.total.confidence,        #not 0.0 as mathematical error
                reason=(f"Arithmetic does not tally correctly: subtotal {invoice.subtotal.value} + tax {invoice.tax.value} + charges {invoice.additional_charges.value} − discount {invoice.discount.value} ≠ total {invoice.total.value}.")
            ))

    return flags    #return flagged fields