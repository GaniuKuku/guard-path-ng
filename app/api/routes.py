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

import sqlparse
import logging

router = APIRouter()
llm_service = LLMService()

logger = logging.getLogger("guardpath")

DEBUG_MODE = False


# =========================================================
# SQL FORMATTER
# =========================================================
def format_sql_query(sql: str) -> str:
    return sqlparse.format(
        sql,
        reindent=True,
        keyword_case="upper"
    )


# =========================================================
# FIELD EXTRACTION
# =========================================================
def extract_requested_fields(prompt: str):
    fields = []
    text = prompt.lower()

    COMMON_FIELDS = [
        "email", "phone", "address", "password",
        "salary", "ssn", "credit_card", "dob", "name"
    ]

    for field in COMMON_FIELDS:
        if field in text:
            fields.append(field)

    return list(set(fields))


# =========================================================
# UNIFIED SCHEMA SCOPE RESOLVER (🔥 FIX)
# =========================================================
def resolve_schema_scope(prompt: str, schema: dict):

    prompt_lower = prompt.lower()
    matched_tables = set()

    for table_name, table_data in schema["tables"].items():

        table_lower = table_name.lower()

        # direct table mention
        if table_lower in prompt_lower:
            matched_tables.add(table_name)

        # column mention
        for col in table_data["columns"]:
            col_name = col["name"].lower()

            if col_name in prompt_lower:
                matched_tables.add(table_name)

    # fallback: if nothing matched, return ALL tables safely
    if not matched_tables:
        matched_tables = set(schema["tables"].keys())

    return list(matched_tables)


# =========================================================
# CORE PIPELINE
# =========================================================
async def process_scan(prompt: str, role: str):

    # -----------------------------------------------------
    # 1. REDACTION
    # -----------------------------------------------------
    redaction_result = redact_sensitive_data(prompt)

    safe_prompt = redaction_result["redacted_prompt"]
    risk_score = redaction_result.get("risk_score", 0)
    risk_level = redaction_result.get("risk_level", "LOW")

    logger.info(f"[REDACTED]: {safe_prompt}")

    # -----------------------------------------------------
    # 2. LOAD SCHEMA
    # -----------------------------------------------------
    schema = get_schema_object()

    all_columns = {
        col["name"].lower()
        for table in schema["tables"].values()
        for col in table["columns"]
    }

    # -----------------------------------------------------
    # 3. FIELD CHECK (SOFT BLOCK)
    # -----------------------------------------------------
    requested_fields = extract_requested_fields(safe_prompt)

    missing_fields = [
        f for f in requested_fields
        if f not in all_columns
    ]

    if missing_fields:

        scoped_tables = resolve_schema_scope(safe_prompt, schema)

        return {
            **redaction_result,
            "original_prompt": prompt,
            "redacted_prompt": safe_prompt,

            "risk_score": 0.9,
            "risk_level": "SCHEMA_MISSING_FIELDS",

            "sql_allowed": False,
            "sql_risks": [],

            "sql_decision_reason":
                f"Database does not contain: {missing_fields}",

            "final_query": None,

            # 🔥 FIXED: always resolved, never empty/None
            "scoped_tables": scoped_tables,

            "message":
                f"Your database does not contain {', '.join(missing_fields)}"
        }

    # -----------------------------------------------------
    # 4. SCHEMA SCOPING (PRIMARY)
    # -----------------------------------------------------
    scoped_schema_obj = get_relevant_schema(safe_prompt)

    if not scoped_schema_obj or not scoped_schema_obj.get("tables"):

        scoped_tables = resolve_schema_scope(safe_prompt, schema)

        return {
            **redaction_result,
            "original_prompt": prompt,
            "redacted_prompt": safe_prompt,

            "risk_score": 1.0,
            "risk_level": "NO_SCHEMA_MATCH",

            "sql_allowed": False,
            "sql_risks": [],

            "sql_decision_reason": "No matching schema found",

            "final_query": None,

            "scoped_tables": scoped_tables,

            "message": "Request does not match database schema"
        }

    # -----------------------------------------------------
    # 5. FORMAT SCHEMA
    # -----------------------------------------------------
    scoped_schema_text = format_schema_for_llm(scoped_schema_obj)

    system_prompt = f"""
You are a SQL generator.

STRICT RULES:
- Output ONLY SQL
- No explanations
- No markdown
- Use ONLY provided schema
- Do NOT invent tables or columns
- NEVER use SELECT *
- Always end query with semicolon

DATABASE SCHEMA:
-----------------
{scoped_schema_text}
-----------------
"""

    # -----------------------------------------------------
    # 6. LLM
    # -----------------------------------------------------
    try:
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

    except Exception as e:
        return {
            **redaction_result,
            "risk_score": 1.0,
            "risk_level": "LLM_ERROR",
            "sql_allowed": False,
            "sql_risks": [],
            "sql_decision_reason": str(e),
            "final_query": None,
            "scoped_tables": []
        }

    if not generated_sql:
        return {
            **redaction_result,
            "risk_score": 1.0,
            "risk_level": "LLM_EMPTY",
            "sql_allowed": False,
            "sql_risks": [],
            "sql_decision_reason": "Empty SQL",
            "final_query": None,
            "scoped_tables": []
        }

    # -----------------------------------------------------
    # 7. FORMAT
    # -----------------------------------------------------
    formatted_sql = format_sql_query(generated_sql)

    # -----------------------------------------------------
    # 8. VALIDATION
    # -----------------------------------------------------
    schema_validation = validate_sql_against_schema(formatted_sql)

    if not schema_validation.get("valid"):
        return {
            **redaction_result,
            "risk_score": 1.0,
            "risk_level": "SCHEMA_VIOLATION",
            "sql_allowed": False,
            "sql_risks": [schema_validation.get("error")],
            "sql_decision_reason": schema_validation.get("error"),
            "final_query": None,
            "scoped_tables": []
        }

    # -----------------------------------------------------
    # 9. FIREWALL
    # -----------------------------------------------------
    sql_result = process_sql(prompt=formatted_sql, role=role)

    if not sql_result.get("allowed", False):
        return {
            **redaction_result,
            "risk_score": 1.0,
            "risk_level": "CRITICAL_SQL",
            "sql_allowed": False,
            "sql_risks": sql_result.get("risks", []),
            "sql_decision_reason": sql_result.get("reason", ""),
            "final_query": None,
            "scoped_tables": []
        }

    # -----------------------------------------------------
    # 10. FINAL RESPONSE
    # -----------------------------------------------------
    response = {
        **redaction_result,
        "original_prompt": prompt,
        "redacted_prompt": safe_prompt,

        "risk_score": risk_score,
        "risk_level": risk_level,

        "sql_allowed": True,
        "sql_risks": sql_result.get("risks", []),
        "sql_decision_reason": sql_result.get("reason", ""),

        "final_query": formatted_sql,

        # 🔥 ALWAYS CONSISTENT NOW
        "scoped_tables": list(scoped_schema_obj["tables"].keys()),

        "message": "SQL query approved"
    }

    if DEBUG_MODE:
        response["system_prompt"] = system_prompt

    return response


# =========================================================
# ROUTES
# =========================================================
@router.post("/scan")
async def scan_prompt(request: PromptRequest):
    return await process_scan(prompt=request.prompt, role="analyst")


@router.get("/debug/schema")
async def debug_schema():
    return {"schema": get_schema_json()}


@router.post("/debug/relevant-schema")
async def debug_relevant_schema(request: PromptRequest):
    return {
        "relevant_schema": get_relevant_schema(request.prompt)
    }
