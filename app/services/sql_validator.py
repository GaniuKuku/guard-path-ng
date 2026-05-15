from app.services.schema_reader import (
    get_schema_object,
    get_semantic_schema_map
)

import sqlglot
from sqlglot import exp


# =========================================================
# UNSAFE SQL KEYWORDS (HARD BLOCK)
# =========================================================
UNSAFE_KEYWORDS = {
    "DROP",
    "DELETE",
    "TRUNCATE",
    "ALTER",
    "GRANT",
    "REVOKE",
    "INSERT",
    "UPDATE",
    "CREATE",
    "REPLACE"
}


# =========================================================
# PLACEHOLDER -> SEMANTIC TYPE
# =========================================================
PLACEHOLDER_TYPES = {
    "<EMAIL>": "email",
    "<PHONE>": "phone",
    "<NAME>": "name"
}


# =========================================================
# PARSE SQL
# =========================================================
def parse_sql(sql: str):

    try:
        return sqlglot.parse_one(sql)

    except Exception:
        return None


# =========================================================
# EXTRACT TABLES
# =========================================================
def extract_tables(ast):

    tables = set()

    for table in ast.find_all(exp.Table):

        if table.name:
            tables.add(table.name.lower())

    return list(tables)


# =========================================================
# EXTRACT COLUMNS
# =========================================================
def extract_columns(ast):

    columns = set()

    for column in ast.find_all(exp.Column):

        if column.name:
            columns.add(column.name.lower())

    return list(columns)


# =========================================================
# SEMANTIC PLACEHOLDER VALIDATION
# Dynamic across ALL databases
# =========================================================
def validate_placeholder_mappings(sql: str, prompt: str):

    semantic_map = get_semantic_schema_map()

    sql_lower = sql.lower()
    prompt_lower = prompt.lower()

    for placeholder, semantic_type in PLACEHOLDER_TYPES.items():

        # only validate placeholders present in prompt
        if placeholder.lower() not in prompt_lower:
            continue

        allowed_columns = [
            item["column"]
            for item in semantic_map.get(semantic_type, [])
        ]

        # no semantic columns exist in DB
        if not allowed_columns:
            return {
                "valid": False,
                "error": (
                    f"No semantic columns found "
                    f"for {placeholder}"
                )
            }

        matched = any(
            column.lower() in sql_lower
            for column in allowed_columns
        )

        if not matched:
            return {
                "valid": False,
                "error": (
                    f"{placeholder} mapped incorrectly"
                )
            }

    return {
        "valid": True,
        "error": None
    }


# =========================================================
# MAIN VALIDATION ENGINE
# =========================================================
def validate_sql_against_schema(
    sql: str,
    prompt: str = ""
):

    # -----------------------------------------------------
    # EMPTY CHECK
    # -----------------------------------------------------
    if not sql or not sql.strip():

        return {
            "valid": False,
            "error": "Empty SQL"
        }

    upper_sql = sql.upper()

    # -----------------------------------------------------
    # HARD BLOCK UNSAFE OPERATIONS
    # -----------------------------------------------------
    for keyword in UNSAFE_KEYWORDS:

        if keyword in upper_sql:

            return {
                "valid": False,
                "error": (
                    f"Unsafe SQL operation detected: "
                    f"{keyword}"
                )
            }

    # -----------------------------------------------------
    # BLOCK SELECT *
    # -----------------------------------------------------
    if "SELECT *" in upper_sql:

        return {
            "valid": False,
            "error": "SELECT * is not allowed"
        }

    # -----------------------------------------------------
    # LOAD SCHEMA
    # -----------------------------------------------------
    schema = get_schema_object()

    allowed_tables = {
        table.lower()
        for table in schema["tables"].keys()
    }

    allowed_columns_by_table = {
        table.lower(): {
            col["name"].lower()
            for col in meta["columns"]
        }
        for table, meta in schema["tables"].items()
    }

    # -----------------------------------------------------
    # PARSE SQL
    # -----------------------------------------------------
    ast = parse_sql(sql)

    if ast is None:

        return {
            "valid": False,
            "error": "Invalid SQL syntax"
        }

    # -----------------------------------------------------
    # EXTRACT TABLES + COLUMNS
    # -----------------------------------------------------
    used_tables = extract_tables(ast)
    used_columns = extract_columns(ast)

    # -----------------------------------------------------
    # TABLE VALIDATION
    # -----------------------------------------------------
    invalid_tables = []

    for table in used_tables:

        if table.lower() not in allowed_tables:
            invalid_tables.append(table)

    if invalid_tables:

        return {
            "valid": False,
            "error": (
                f"Invalid table(s): "
                f"{invalid_tables}"
            )
        }

    # -----------------------------------------------------
    # COLUMN VALIDATION
    # -----------------------------------------------------
    invalid_columns = []

    for col in used_columns:

        found = False

        for table_cols in allowed_columns_by_table.values():

            if col.lower() in table_cols:
                found = True
                break

        if not found:
            invalid_columns.append(col)

    if invalid_columns:

        return {
            "valid": False,
            "error": (
                f"Invalid column(s): "
                f"{invalid_columns}"
            )
        }

    # -----------------------------------------------------
    # SEMANTIC VALIDATION
    # Dynamic PII mapping protection
    # -----------------------------------------------------
    semantic_validation = validate_placeholder_mappings(
        sql=sql,
        prompt=prompt
    )

    if not semantic_validation["valid"]:

        return {
            "valid": False,
            "error": semantic_validation["error"]
        }

    # -----------------------------------------------------
    # FINAL PASS
    # -----------------------------------------------------
    return {
        "valid": True,
        "error": None
    }
