"""
test_confidence_router.py

Covers the confidence router (the brief's core requirement) and our
deterministic rule-based checks that run regardless of the model's
self-reported confidence.

Router rule (brief): any field with confidence < REVIEW_THRESHOLD (0.75) is
flagged and the document goes to pending_review; if nothing is flagged it is
auto_approved.
"""

from app.schemas import InvoiceSchema
from app.extraction import (
    route_by_confidence, deterministic_rule_based_flags, SCALAR_FIELDS,
)


def route(valid_invoice_dict, **over):
    invoice = InvoiceSchema.model_validate(valid_invoice_dict(**over))
    return route_by_confidence(invoice)


# --------------------------------------------------------------------------- #
# Auto-approve vs. pending_review
# --------------------------------------------------------------------------- #
def test_all_high_confidence_auto_approves(valid_invoice_dict):
    status, flagged = route(valid_invoice_dict)
    assert status == "auto_approved"
    assert flagged == []


def test_low_confidence_field_is_flagged(valid_invoice_dict):
    status, flagged = route(valid_invoice_dict, total_conf=0.40)
    assert status == "pending_review"
    paths = [f.field_path for f in flagged]
    assert "total" in paths


def test_threshold_is_strictly_less_than(valid_invoice_dict):
    """Exactly 0.75 must NOT be flagged (rule is < 0.75, not <=)."""
    status, flagged = route(valid_invoice_dict,
                            vendor_conf=0.75, invoice_number_conf=0.75,
                            date_conf=0.75, currency_conf=0.75,
                            subtotal_conf=0.75, tax_conf=0.75,
                            discount_conf=0.75, additional_charges_conf=0.75,
                            total_conf=0.75)
    # None of the confidence values are below 0.75, so no confidence flags.
    conf_flags = [f for f in flagged
                  if "confidence" in (f.reason or "").lower()]
    assert conf_flags == []


def test_just_below_threshold_is_flagged(valid_invoice_dict):
    status, flagged = route(valid_invoice_dict, vendor_conf=0.749)
    assert status == "pending_review"
    assert "vendor" in [f.field_path for f in flagged]


def test_flagged_field_carries_confidence_and_reason(valid_invoice_dict):
    _, flagged = route(valid_invoice_dict, currency_conf=0.30)
    f = next(x for x in flagged if x.field_path == "currency")
    assert f.confidence == 0.30
    assert f.reason  # non-empty explanation


def test_low_confidence_line_item_flagged(valid_invoice_dict):
    items = [{"description": "Blurry", "quantity": 1.0, "unit_price": 100.0,
              "amount": 100.0, "confidence": 0.20}]
    status, flagged = route(valid_invoice_dict, line_items=items)
    assert status == "pending_review"
    assert any(f.field_path.startswith("line_items[") for f in flagged)


def test_scalar_fields_constant_covers_our_additions():
    assert "discount" in SCALAR_FIELDS
    assert "additional_charges" in SCALAR_FIELDS


# --------------------------------------------------------------------------- #
# Deterministic rule-based flags (independent of model confidence)
# --------------------------------------------------------------------------- #
def test_confident_zeros_still_flagged(valid_invoice_dict):
    """
    The key non-receipt case: the model returns empty/zero values but with
    HIGH confidence. The confidence router alone would auto-approve it; the
    deterministic checks must catch it.
    """
    status, flagged = route(
        valid_invoice_dict,
        vendor="", vendor_conf=0.99,
        total=0.0, total_conf=0.99,
        subtotal=0.0, tax=0.0, discount=0.0, additional_charges=0.0,
        line_items=[],
    )
    assert status == "pending_review"
    paths = [f.field_path for f in flagged]
    assert "vendor" in paths       # empty vendor
    assert "total" in paths        # zero total
    assert "line_items" in paths   # no items


def test_empty_vendor_flagged(valid_invoice_dict):
    invoice = InvoiceSchema.model_validate(
        valid_invoice_dict(vendor="", vendor_conf=0.99))
    flags = deterministic_rule_based_flags(invoice)
    assert any(f.field_path == "vendor" for f in flags)


def test_zero_total_flagged(valid_invoice_dict):
    invoice = InvoiceSchema.model_validate(
        valid_invoice_dict(total=0.0, total_conf=0.99))
    flags = deterministic_rule_based_flags(invoice)
    assert any(f.field_path == "total" for f in flags)


def test_no_line_items_flagged(valid_invoice_dict):
    invoice = InvoiceSchema.model_validate(
        valid_invoice_dict(line_items=[]))
    flags = deterministic_rule_based_flags(invoice)
    assert any(f.field_path == "line_items" for f in flags)


# --------------------------------------------------------------------------- #
# Arithmetic reconciliation
# --------------------------------------------------------------------------- #
def test_reconciling_totals_not_flagged(valid_invoice_dict):
    """subtotal 100 + tax 10 + charges 0 - discount 0 = 110 (total). Clean."""
    invoice = InvoiceSchema.model_validate(valid_invoice_dict())
    flags = deterministic_rule_based_flags(invoice)
    assert not any(f.field_path == "total" and "tally" in (f.reason or "").lower()
                   for f in flags)


def test_broken_arithmetic_flagged(valid_invoice_dict):
    """100 + 10 + 0 - 0 = 110, but total says 999 -> reconciliation flag."""
    invoice = InvoiceSchema.model_validate(
        valid_invoice_dict(total=999.0))
    flags = deterministic_rule_based_flags(invoice)
    assert any(f.field_path == "total" for f in flags)


def test_discount_pending_interpretation_accepted(valid_invoice_dict):
    """
    Our reconciliation accepts EITHER discount-already-applied OR
    discount-pending. subtotal 100 + tax 10 + 0 = 110; with a discount of 10
    the 'pending' reading is 110 - 10 = 100. If total is 110 (discount not yet
    subtracted) it should still reconcile under the applied reading.
    """
    invoice = InvoiceSchema.model_validate(
        valid_invoice_dict(discount=10.0, total=110.0))
    flags = deterministic_rule_based_flags(invoice)
    # base = 100+10+0 = 110 == total 110 -> applied reading holds, no flag
    assert not any(f.field_path == "total" for f in flags)


def test_discount_applied_interpretation_accepted(valid_invoice_dict):
    """base - discount = total also reconciles: 110 - 10 = 100."""
    invoice = InvoiceSchema.model_validate(
        valid_invoice_dict(discount=10.0, total=100.0))
    flags = deterministic_rule_based_flags(invoice)
    assert not any(f.field_path == "total" for f in flags)


def test_additional_charges_included_in_reconciliation(valid_invoice_dict):
    """100 + 10 + 5 - 0 = 115 reconciles when charges are 5 and total 115."""
    invoice = InvoiceSchema.model_validate(
        valid_invoice_dict(additional_charges=5.0, total=115.0))
    flags = deterministic_rule_based_flags(invoice)
    assert not any(f.field_path == "total" for f in flags)
