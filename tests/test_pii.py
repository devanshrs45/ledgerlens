from app.pii import (
    redact, redact_all_pii, verhoeff_pattern_check, REDACTION_TOKEN,
)

TOKEN = REDACTION_TOKEN


def test_email_redacted():
    out = redact("contact me at alice.smith@example.co.in please")
    assert "alice.smith@example.co.in" not in out
    assert TOKEN in out


def test_ssn_redacted():
    out = redact("SSN 123-45-6789 on file")
    assert "123-45-6789" not in out
    assert TOKEN in out


def test_phone_redacted():
    out = redact("call +91 98765 43210 today")
    assert "98765 43210" not in out
    assert TOKEN in out


def test_pan_redacted():
    out = redact("PAN ABCDE1234F issued")
    assert "ABCDE1234F" not in out
    assert TOKEN in out


def test_gstin_redacted():
    out = redact("GSTIN 22AAAAA0000A1Z5 on invoice")
    assert "22AAAAA0000A1Z5" not in out
    assert TOKEN in out


def test_card_number_redacted():
    out = redact("card 4111 1111 1111 1111 charged")
    assert "4111 1111 1111 1111" not in out
    assert TOKEN in out


def test_iso_date_not_redacted_as_phone():
    out = redact("date 2026-07-12 total 110")
    assert "2026-07-12" in out


def test_short_number_not_redacted():
    out = redact("qty 3 price 25")
    assert "3" in out and "25" in out
    assert TOKEN not in out


def test_valid_aadhaar_redacted():
    candidate = _find_valid_aadhaar()
    spaced = f"{candidate[:4]} {candidate[4:8]} {candidate[8:]}"
    out = redact(f"aadhaar {spaced} enrolled")
    assert spaced not in out
    assert TOKEN in out


def test_invoice_number_not_redacted_as_aadhaar():
    from app.pii import redact_aadhar
    import re
    invalid = _find_invalid_aadhaar()
    assert verhoeff_pattern_check(invalid) is False
    m = re.match(r"(\d{12})", invalid)
    assert redact_aadhar(m) == invalid


def test_verhoeff_checker_basic():
    valid = _find_valid_aadhaar()
    assert verhoeff_pattern_check(valid) is True
    mangled = ("1" if valid[0] != "1" else "2") + valid[1:]
    assert verhoeff_pattern_check(mangled) is False


def test_verhoeff_rejects_wrong_length():
    assert verhoeff_pattern_check("123") is False
    assert verhoeff_pattern_check("12345678901234") is False


def test_redact_all_pii_returns_string():
    out = redact_all_pii('{"vendor":"Shop","email":"a@b.com"}')
    assert isinstance(out, str)
    assert "a@b.com" not in out


def test_redact_all_pii_truncates():
    long_text = "x" * 5000
    out = redact_all_pii(long_text, max_len=100)
    assert len(out) <= 100


def test_redact_empty_string():
    assert redact("") == ""


def test_redact_preserves_clean_text():
    clean = "vendor Corner Shop total 110 currency INR"
    assert redact(clean) == clean


def _find_valid_aadhaar():
    base = 234123456780
    for n in range(base, base + 100):
        s = str(n)
        if len(s) == 12 and s[0] in "23456789" and verhoeff_pattern_check(s):
            return s
    raise AssertionError("no valid Aadhaar found in search range")


def _find_invalid_aadhaar():
    base = 234123456780
    for n in range(base, base + 100):
        s = str(n)
        if len(s) == 12 and s[0] in "23456789" and not verhoeff_pattern_check(s):
            return s
    raise AssertionError("no invalid Aadhaar found in search range")
