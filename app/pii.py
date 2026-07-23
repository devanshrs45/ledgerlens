import re
_PATTERNS = [
    re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),        #Email id
    re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}Z[A-Z\d]{1}\b"),     #GSTIN number
    re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),     #PAN Number
    re.compile(r"\b(?:\d[ -]?){13,16}\b"),       #Card number
    re.compile(r"\b[2-9]\d{3}\s?\d{4}\s?\d{4}\b"),   #Aadhar Number     --ToDo VEROEHF-- DOWN
    re.compile(r"\b[\w.\-]{2,}@(?:ok\w+|paytm|ybl|upi|axl|ibl)\b")     #UPI id
]

_PHONE_CANDIDATE = re.compile(r"(?<!\d)(\+?\d[\d\s().-]{8,}\d)(?!\d)")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

REDACTION_TOKEN = "[REDACTED]"

def _phone_sub(match: re.Match) -> str:
    candidate = match.group(0)
    digits = sum(c.isdigit() for c in candidate)
    if (digits >= 10) and (not _ISO_DATE.match(candidate.strip())):
        return REDACTION_TOKEN
    return candidate

def redact(text: str) -> str:
    if not text:
        return text
    out = text
    for pattern in _PATTERNS:
        out = pattern.sub(REDACTION_TOKEN, out)

    return _PHONE_CANDIDATE.sub(_phone_sub, out)

def safe_log_payload(payload: str, max_len: int = 2000) -> str:
    return redact(payload)[:max_len]





#AAdhar
'''
_AADHAAR_CANDIDATE = re.compile(r"\b[2-9]\d{3}\s?\d{4}\s?\d{4}\b")   

_VERHOEFF_D = (
    (0,1,2,3,4,5,6,7,8,9),(1,2,3,4,0,6,7,8,9,5),(2,3,4,0,1,7,8,9,5,6),
    (3,4,0,1,2,8,9,5,6,7),(4,0,1,2,3,9,5,6,7,8),(5,9,8,7,6,0,4,3,2,1),
    (6,5,9,8,7,1,0,4,3,2),(7,6,5,9,8,2,1,0,4,3),(8,7,6,5,9,3,2,1,0,4),
    (9,8,7,6,5,4,3,2,1,0),
)
_VERHOEFF_P = (
    (0,1,2,3,4,5,6,7,8,9),(1,5,7,6,2,8,3,0,9,4),(5,8,0,3,7,9,6,1,4,2),
    (8,9,1,6,0,4,3,5,2,7),(9,4,5,3,1,2,6,8,7,0),(4,2,8,6,5,7,3,9,0,1),
    (2,7,9,3,8,0,6,4,1,5),(7,0,4,6,9,1,3,2,5,8),
)

def verhoeff_valid(number: str) -> bool:
    """True if `number` is 12 digits and passes the Verhoeff checksum."""
    if len(number) != 12 or not number.isdigit():
        return False
    checksum = 0
    for i, digit in enumerate(reversed(number)):
        checksum = _VERHOEFF_D[checksum][_VERHOEFF_P[i % 8][int(digit)]]
    return checksum == 0

    
def redact(text: str) -> str:
    if not text:
        return text
    out = text
    for pattern in _PATTERNS:
        out = pattern.sub(REDACTION_TOKEN, out)
    out = _AADHAAR_CANDIDATE.sub(_aadhaar_sub, out)   # ← the missing line
    return _PHONE_CANDIDATE.sub(_phone_sub, out)


def _aadhaar_sub(match):
    candidate = match.group(0)
    digits = re.sub(r"\D", "", candidate)
    return REDACTION_TOKEN if verhoeff_valid(digits) else candidate
'''