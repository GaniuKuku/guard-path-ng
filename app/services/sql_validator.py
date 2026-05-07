UNSAFE_KEYWORDS = [
    "DROP",
    "DELETE",
    "TRUNCATE"
]


def validate_sql(prompt: str):

    risks = []

    upper_prompt = prompt.upper()

    for keyword in UNSAFE_KEYWORDS:

        if keyword in upper_prompt:
            risks.append(f"Unsafe SQL keyword detected: {keyword}")

    if "SELECT *" in upper_prompt:
        risks.append("SELECT * detected")

    return risks
