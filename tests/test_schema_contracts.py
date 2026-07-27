import pytest
from pydantic import ValidationError
from app.schemas import InvoiceSchema, ConfidentStr, ConfidentFloat, LineItem, FlaggedField, ExtractionResult, ReviewItem, ApproveRequest, ApproveResponse, RejectRequest, RejectResponse, FieldCorrection, DocumentSummary



def test_invoice_schema_round_trips_json(valid_invoice_dict):
    """Serialise to JSON and parse back; the result must equal the original."""
    invoice = InvoiceSchema.model_validate(valid_invoice_dict())
    as_json = invoice.model_dump_json()
    restored = InvoiceSchema.model_validate_json(as_json)
    assert restored == invoice


def test_invoice_schema_accepts_model_dump_reparse(valid_invoice_dict):
    """model_dump() -> model_validate() also round-trips (dict path)."""
    invoice = InvoiceSchema.model_validate(valid_invoice_dict())
    restored = InvoiceSchema.model_validate(invoice.model_dump())
    assert restored == invoice


# --------------------------------------------------------------------------- #
# Field presence: the schema must carry everything the app reads
# --------------------------------------------------------------------------- #
def test_invoice_has_all_scalar_fields(valid_invoice_dict):
    invoice = InvoiceSchema.model_validate(valid_invoice_dict())
    for name in ("vendor", "invoice_number", "date", "currency",
                 "subtotal", "tax", "discount", "additional_charges", "total"):
        assert hasattr(invoice, name), f"missing field {name}"


def test_invoice_has_our_added_fields(valid_invoice_dict):
    """discount and additional_charges are our additions beyond the brief."""
    invoice = InvoiceSchema.model_validate(valid_invoice_dict())
    assert isinstance(invoice.discount, ConfidentFloat)
    assert isinstance(invoice.additional_charges, ConfidentFloat)


def test_scalar_fields_are_confident_wrappers(valid_invoice_dict):
    """Each scalar is a value+confidence object, not a bare value."""
    invoice = InvoiceSchema.model_validate(valid_invoice_dict())
    assert isinstance(invoice.vendor, ConfidentStr)
    assert isinstance(invoice.total, ConfidentFloat)
    assert hasattr(invoice.vendor, "confidence")
    assert hasattr(invoice.total, "confidence")


# --------------------------------------------------------------------------- #
# Confidence bounds are enforced (ge=0, le=1)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("bad", [1.5, -0.1, 2.0])
def test_confidence_above_or_below_bounds_rejected(bad):
    with pytest.raises(ValidationError):
        ConfidentStr(value="x", confidence=bad)


@pytest.mark.parametrize("good", [0.0, 0.5, 1.0])
def test_confidence_within_bounds_accepted(good):
    node = ConfidentFloat(value=1.0, confidence=good)
    assert node.confidence == good


def test_overall_confidence_bounds(valid_invoice_dict):
    with pytest.raises(ValidationError):
        InvoiceSchema.model_validate(valid_invoice_dict(overall_confidence=1.4))


# --------------------------------------------------------------------------- #
# LineItem contract (matches the brief's named tuple of fields)
# --------------------------------------------------------------------------- #
def test_line_item_fields():
    item = LineItem(description="A", quantity=2, unit_price=5.0,
                    amount=10.0, confidence=0.9)
    assert item.description == "A"
    assert item.amount == 10.0


def test_malformed_json_raises(valid_invoice_dict):
    """A confidence that is not a number must fail loudly, not silently pass."""
    bad = valid_invoice_dict()
    bad["total"]["confidence"] = "not-a-number"
    with pytest.raises(ValidationError):
        InvoiceSchema.model_validate(bad)


# --------------------------------------------------------------------------- #
# FlaggedField carries the reason we thread through the pipeline
# --------------------------------------------------------------------------- #
def test_flagged_field_has_reason():
    f = FlaggedField(field_path="total", value="0", confidence=0.0,
                     reason="Total is zero.")
    assert f.reason == "Total is zero."


def test_flagged_field_reason_optional():
    """reason has a default so older construction sites do not break."""
    f = FlaggedField(field_path="total", value="0", confidence=0.0)
    assert f.reason == "" or f.reason is None


# --------------------------------------------------------------------------- #
# API request/response models exist and construct
# --------------------------------------------------------------------------- #
def test_api_models_construct():
    assert ApproveRequest(doc_id="d1", corrections=[]).doc_id == "d1"
    assert ApproveResponse(doc_id="d1", status="approved",
                           applied_corrections=0).status == "approved"
    assert RejectRequest(doc_id="d1", reason="bad").reason == "bad"
    assert RejectResponse(doc_id="d1", status="rejected").status == "rejected"
    assert FieldCorrection(field_path="total",
                           corrected_value="110").corrected_value == "110"


def test_reject_reason_defaults_empty():
    assert RejectRequest(doc_id="d1").reason == ""


def test_extraction_result_optional_extraction():
    """A blocked doc has no extraction; the field must allow None."""
    r = ExtractionResult(doc_id="d1", filename="x.png", status="blocked",
                         blocked_reason="nsfw")
    assert r.extraction is None
    assert r.flagged_fields == []
