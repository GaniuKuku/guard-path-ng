from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
from presidio_analyzer.nlp_engine import NlpEngineProvider
from datetime import datetime


# 1. NLP ENGINE SETUP (spaCy)


nlp_configuration = {
    "nlp_engine_name": "spacy",
    "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}]
}

provider = NlpEngineProvider(nlp_configuration=nlp_configuration)
nlp_engine = provider.create_engine()

analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
anonymizer = AnonymizerEngine()


# 2. CONTEXT-AWARE NIGERIAN PII PATTERNS


nin_pattern = Pattern(name="nin_context", regex=r"(?i)(?:nin|national identification number|national id)[^\d]*(\d{11})", score=0.95)
nin_recognizer = PatternRecognizer(supported_entity="NGA_NIN", patterns=[nin_pattern])

bvn_pattern = Pattern(name="bvn_context", regex=r"(?i)(?:bvn|bank verification number)[^\d]*(\d{11})", score=0.95)
bvn_recognizer = PatternRecognizer(supported_entity="NGA_BVN", patterns=[bvn_pattern])

nuban_pattern = Pattern(name="nuban_regex", regex=r"\b\d{10}\b", score=0.90)
nuban_recognizer = PatternRecognizer(supported_entity="NGA_NUBAN", patterns=[nuban_pattern], context=["account", "nuban", "acct"])

phone_pattern = Pattern(name="nga_phone_regex", regex=r"\b(?:\+234|0)[789][01]\d{8}\b", score=0.90)
phone_recognizer = PatternRecognizer(supported_entity="NGA_PHONE", patterns=[phone_pattern])

analyzer.registry.add_recognizer(nin_recognizer)
analyzer.registry.add_recognizer(bvn_recognizer)
analyzer.registry.add_recognizer(nuban_recognizer)
analyzer.registry.add_recognizer(phone_recognizer)


# 3. ENTITY NORMALIZATION LAYER


ENTITY_NORMALIZATION = {
    "NGA_NIN": "NIN",
    "NGA_BVN": "BVN",
    "NGA_NUBAN": "BANK_ACCOUNT",
    "NGA_PHONE": "PHONE",
    "EMAIL_ADDRESS": "EMAIL",
    "CREDIT_CARD": "CREDIT_CARD",
    "PERSON": "PERSON",
    "LOCATION": "LOCATION"
}


# 4. CUSTOM ANONYMIZATION OPERATORS


CUSTOM_OPERATORS = {
    "NGA_NIN": OperatorConfig("replace", {"new_value": "<NIN>"}),
    "NGA_BVN": OperatorConfig("replace", {"new_value": "<BVN>"}),
    "NGA_NUBAN": OperatorConfig("replace", {"new_value": "<BANK_ACCOUNT>"}),
    "NGA_PHONE": OperatorConfig("replace", {"new_value": "<PHONE>"}),
    "EMAIL_ADDRESS": OperatorConfig("replace", {"new_value": "<EMAIL>"}),
    "PERSON": OperatorConfig("replace", {"new_value": "<PERSON>"}),
    "LOCATION": OperatorConfig("replace", {"new_value": "<LOCATION>"}),
    "CREDIT_CARD": OperatorConfig("replace", {"new_value": "<CREDIT_CARD>"})
}


# 5. RISK SCORING ENGINE & CLASSIFICATION


RISK_WEIGHTS = {
    "NIN": 0.98,
    "BVN": 0.95,
    "BANK_ACCOUNT": 0.85,
    "PHONE": 0.65,
    "EMAIL": 0.70,
    "CREDIT_CARD": 0.98,
    "PERSON": 0.40,
    "LOCATION": 0.20,
    "IP_ADDRESS": 0.40
}

def calculate_risk(results):

    if not results:
        return 0.0

    highest_risk = 0.0

    for r in results:

        entity = ENTITY_NORMALIZATION.get(
            r.entity_type,
            r.entity_type
        )

        weight = RISK_WEIGHTS.get(entity, 0.3)

        item_risk = weight * r.score

        highest_risk = max(
            highest_risk,
            item_risk
        )

    return round(min(highest_risk, 1.0), 3)

# 6. CORE REDACTION FUNCTION
def extract_entities(results):

    return [
        {
            "entity": ENTITY_NORMALIZATION.get(
                r.entity_type,
                r.entity_type
            ),
            "score": round(r.score, 3),
            "start": r.start,
            "end": r.end
        }
        for r in results
    ]

def get_risk_level(score: float) -> str:

    if score >= 0.7:
        return "HIGH"
    elif score >= 0.4:
        return "MEDIUM"
    else:
        return "LOW"

def redact_sensitive_data(prompt: str):

    # =========================================================
    # ENTERPRISE ENTITY WHITELIST
    # =========================================================

    allowed_entities = [
        "NGA_NIN",
        "NGA_BVN",
        "NGA_NUBAN",
        "NGA_PHONE",
        "EMAIL_ADDRESS",
        "CREDIT_CARD",
        "PERSON",
        "LOCATION",
        "IP_ADDRESS"
    ]

    # =========================================================
    # ANALYZE PROMPT
    # =========================================================

    raw_results = analyzer.analyze(
        text=prompt,
        language="en",
        entities=allowed_entities
    )

    # =========================================================
    # DUPLICATE FILTERING
    # =========================================================

    results = []

    seen = set()

    for r in raw_results:

        key = (r.start, r.end, r.entity_type)

        if key not in seen:
            results.append(r)
            seen.add(key)

    # =========================================================
    # ANONYMIZATION
    # =========================================================

    anonymized_result = anonymizer.anonymize(
        text=prompt,
        analyzer_results=results,
        operators=CUSTOM_OPERATORS
    )

    # =========================================================
    # SCORING & METADATA
    # =========================================================

    risk_score = calculate_risk(results)

    entities = extract_entities(results)

    detected_types = list(set(
        ENTITY_NORMALIZATION.get(
            r.entity_type,
            r.entity_type
        )
        for r in results
    ))

    # =========================================================
    # RESPONSE PAYLOAD
    # =========================================================

    return {
        "original_prompt": prompt,
        "redacted_prompt": anonymized_result.text,
        "risk_score": risk_score,
        "risk_level": get_risk_level(risk_score),
        "detected_entities": detected_types,
        "entity_details": entities,
        "scanned_at": datetime.utcnow().isoformat() + "Z"
    }
