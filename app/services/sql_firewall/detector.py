import re


# =========================================================
# BASIC SQL DETECTION
# =========================================================

SQL_PATTERN = re.compile(
    r"\b("
    r"SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE"
    r")\b",
    re.IGNORECASE
)


def looks_like_sql(prompt: str) -> bool:

    if not prompt:
        return False

    return bool(SQL_PATTERN.search(prompt))
