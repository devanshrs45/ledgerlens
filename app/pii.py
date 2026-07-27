'''
pii.py -> Redacts personal information:
- SSN, Email, Phone, Card, GSTIN, PAN, Aadhar to "[REDACTED]" using regex
- Aadhar uses Veroeff pattern, otherwise it might have redacted invoice numbers
- Phone number so that it does not redact date bymistake
'''

import re
_PATTERNS = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),   #SSN (for usa id)
    re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),        #Email id
    re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}Z[A-Z\d]{1}\b"),     #GSTIN number
    re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),     #PAN Number
    re.compile(r"\b(?:\d[ -]?){13,16}\b"),       #Card number
]

PHONE_CANDIDATE = re.compile(r"(?<!\d)(\+?\d[\d\s().-]{8,}\d)(?!\d)")      #Phone format
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")                              #ido date format (for phone check)
AADHAR_CANDIDATE = re.compile(r"\b[2-9]\d{3}\s?\d{4}\s?\d{4}\b")          #aadhar format

REDACTION_TOKEN = "[REDACTED]"      #To replace PII with this


#Verhoeff pattern for aadhar
VERHOEFF_D = (
    (0,1,2,3,4,5,6,7,8,9),(1,2,3,4,0,6,7,8,9,5),(2,3,4,0,1,7,8,9,5,6),
    (3,4,0,1,2,8,9,5,6,7),(4,0,1,2,3,9,5,6,7,8),(5,9,8,7,6,0,4,3,2,1),
    (6,5,9,8,7,1,0,4,3,2),(7,6,5,9,8,2,1,0,4,3),(8,7,6,5,9,3,2,1,0,4),
    (9,8,7,6,5,4,3,2,1,0),
)
VERHOEFF_P = (
    (0,1,2,3,4,5,6,7,8,9),(1,5,7,6,2,8,3,0,9,4),(5,8,0,3,7,9,6,1,4,2),
    (8,9,1,6,0,4,3,5,2,7),(9,4,5,3,1,2,6,8,7,0),(4,2,8,6,5,7,3,9,0,1),
    (2,7,9,3,8,0,6,4,1,5),(7,0,4,6,9,1,3,2,5,8),
)

#Checks if number is aadhar using verhoeff
def verhoeff_pattern_check(number: str) -> bool:
    if len(number) != 12 or not number.isdigit():
        return False
    check = 0
    for i, digit in enumerate(reversed(number)):
        check = VERHOEFF_D[check][VERHOEFF_P[i % 8][int(digit)]]
    return check == 0


#to redact aadhar and check it matches the pattenr
def redact_aadhar(match: re.Match) -> str:
    candidate = match.group(0)
    digits = re.sub(r"\D", "", candidate)          
    return REDACTION_TOKEN if verhoeff_pattern_check(digits) else candidate

#To redact phone and check if its not ISO date
def redact_phone(match: re.Match) -> str:
    candidate = match.group(0)
    digits = sum(c.isdigit() for c in candidate)
    if (digits >= 10) and (not ISO_DATE.match(candidate.strip())):
        return REDACTION_TOKEN
    return candidate


#Redaction of all patterns
def redact(text: str) -> str:
    if not text:
        return text
    out = text
    for pattern in _PATTERNS:
        out = pattern.sub(REDACTION_TOKEN, out)
    out = AADHAR_CANDIDATE.sub(redact_aadhar, out)   
    out = PHONE_CANDIDATE.sub(redact_phone, out)    
    return out  


#the function actually called by others
def redact_all_pii(payload: str, max_len: int = 2000) -> str:
    return redact(payload)[:max_len]




