from fastapi import APIRouter
from app.schemas.prompt_schema import PromptRequest
from app.services.redactor import redact_sensitive_data
from app.services.sql_firewall.engine import process_sql
from app.services.sql_validator import validate_sql_against_schema
from app.llm.service import LLMService

from app.services.schema_reader import (
    get_schema_json,
    get_relevant_schema,
    format_schema_for_llm,
    get_schema_object
)

from app.services.prompt_builder import build_system_prompt

import sqlparse
import logging
import re

router = APIRouter()
llm_service = LLMService()
logger = logging.getLogger("guardpath")

DEBUG_MODE = False


# =========================================================
# SQL FORMATTER
# =========================================================
def format_sql_query(sql: str):
    return sqlparse.format(sql, reindent=True, keyword_case="upper")


# =========================================================
# INTENT DETECTOR
# =========================================================
def contains_dangerous_intent(prompt: str):
    text = prompt.lower()

    dangerous_keywords = [
        "drop", "delete", "truncate",
        "alter", "update", "insert"
    ]

    for keyword in dangerous_keywords:
        if re.search(rf"\b{keyword}\b", text):
            return True, keyword

    return False, None


# =========================================================
# FIELD EXTRACTION (kept lightweight)
# =========================================================
def extract_requested_fields(prompt: str):
    text = prompt.lower()

    FIELD_ALIASES = {
        "email": ["email", "gmail", "mail"],
        "phone": ["phone", "mobile", "telephone"],
        "address": ["address", "location"],
        "salary": ["salary", "income", "wage"],
        "dob": ["dob", "date of birth"]
    }

    detected = set()

    for canonical, aliases in FIELD_ALIASES.items():
        for a in aliases:
            if a in text:
                detected.add(canonical)

    return list(detected)


# =========================================================
# SEMANTIC CHECK
# =========================================================
def field_exists(field: str, all_columns: set):
    field = field.lower()

    if field in all_columns:
        return True

    for col in all_columns:
        if field in col.replace("_", " "):
            return True

    return False


# =========================================================
# SCHEMA SCOPE RESOLVER
# =========================================================
def resolve_schema_scope(prompt: str, schema: dict):

    prompt_lower = prompt.lower()
    matched = set()

    for table_name, table_data in schema["tables"].items():

        if table_name.lower() in prompt_lower:
            matched.add(table_name)

        for col in table_data["columns"]:
            col_name = col["name"].lower()

            if col_name in prompt_lower:
                matched.add(table_name)

            if col_name.replace("_", " ") in prompt_lower:
                matched.add(table_name)

    if not matched:
        matched = set(schema["tables"].keys())

    return list(matched)


# =========================================================
# MAIN PIPELINE
# =========================================================
async def process_scan(prompt: str, role: str):

    # 1. REDACTION
    redaction_result = redact_sensitive_data(prompt)
    safe_prompt = redaction_result["redacted_prompt"]

    # 2. LOAD SCHEMA
    schema = get_schema_object()

    all_columns = {
        col["name"].lower()
        for t in schema["tables"].values()
        for col in t["columns"]
    }

    scoped_tables = resolve_schema_scope(prompt, schema)

    # 3. DANGEROUS INTENT BLOCK
    dangerous, keyword = contains_dangerous_intent(prompt)
    if dangerous:
        return {
            **redaction_result,
            "risk_level": "CRITICAL_SQL",
            "sql_allowed": False,
            "sql_decision_reason": f"Blocked {keyword}",
            "final_query": None,
            "scoped_tables": scoped_tables
        }

    # 4. FIELD CHECK
    requested = extract_requested_fields(prompt)

    missing = [
        f for f in requested
        if not field_exists(f, all_columns)
    ]

    if missing:
        return {
            **redaction_result,
            "risk_level": "SCHEMA_MISSING_FIELDS",
            "sql_allowed": False,
            "sql_decision_reason": f"Missing fields: {missing}",
            "final_query": None,
            "scoped_tables": scoped_tables
        }

    # 5. GET SCOPED SCHEMA
    scoped_schema = get_relevant_schema(prompt)

    if not scoped_schema or not scoped_schema.get("tables"):
        return {
            **redaction_result,
            "risk_level": "NO_SCHEMA_MATCH",
            "sql_allowed": False,
            "final_query": None,
            "scoped_tables": scoped_tables
        }

    schema_text = format_schema_for_llm(scoped_schema)

    # 6. BUILD PROMPT (🔥 MOVED OUT)
    system_prompt = build_system_prompt(
        dialect="postgres",
        schema_text=schema_text
    )

    # 7. LLM CALL
    llm_response = await llm_service.generate(
        prompt=safe_prompt,
        system_prompt=system_prompt,
        temperature=0.1
    )

    generated_sql = (
        llm_response.get("text")
        or llm_response.get("content")
        or ""
    ).strip()

    if not generated_sql:
        return {
            **redaction_result,
            "risk_level": "LLM_EMPTY",
            "sql_allowed": False,
            "final_query": None,
            "scoped_tables": scoped_tables
        }

    # 8. FORMAT
    formatted_sql = format_sql_query(generated_sql)

    # 9. VALIDATE
    validation = validate_sql_against_schema(formatted_sql)

    if not validation.get("valid"):
        return {
            **redaction_result,
            "risk_level": "SCHEMA_VIOLATION",
            "sql_allowed": False,
            "sql_decision_reason": validation.get("error"),
            "final_query": None,
            "scoped_tables": scoped_tables
        }

    # 10. FIREWALL
    result = process_sql(prompt=formatted_sql, role=role)

    if not result.get("allowed"):
        return {
            **redaction_result,
            "risk_level": "CRITICAL_SQL",
            "sql_allowed": False,
            "sql_decision_reason": result.get("reason"),
            "final_query": None,
            "scoped_tables": scoped_tables
        }

    # 11. SUCCESS
    return {
        **redaction_result,
        "risk_level": "LOW",
        "sql_allowed": True,
        "sql_risks": result.get("risks", []),
        "sql_decision_reason": result.get("reason", ""),
        "final_query": formatted_sql,
        "scoped_tables": list(scoped_schema["tables"].keys()),
        "message": "SQL query approved"
    }


# ROUTES
@router.post("/scan")
async def scan_prompt(request: PromptRequest):
    return await process_scan(request.prompt, "analyst")


@router.get("/debug/schema")
async def debug_schema():
    return {"schema": get_schema_json()}
