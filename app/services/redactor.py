import re

BVN_PATTERN = r"\b\d{11}\b"

PHONE_PATTERN = r"\b(?:\+234|0)[789][01]\d{8}\b"

ACCOUNT_PATTERN = r"\b\d{10}\b"


def redact_sensitive_data(text: str):

    detected = []

    # BVN
    if re.search(BVN_PATTERN, text):
        detected.append("BVN")
        text = re.sub(BVN_PATTERN, "[REDACTED_BVN]", text)

    # Phone
    if re.search(PHONE_PATTERN, text):
        detected.append("PHONE_NUMBER")
        text = re.sub(PHONE_PATTERN, "[REDACTED_PHONE]", text)

    # Account Number
    if re.search(ACCOUNT_PATTERN, text):
        detected.append("ACCOUNT_NUMBER")
        text = re.sub(ACCOUNT_PATTERN, "[REDACTED_ACCOUNT]", text)

    return text, detected
