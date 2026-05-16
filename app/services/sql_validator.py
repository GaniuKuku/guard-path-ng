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
# EXTRACT REAL COLUMNS ONLY
# Ignores:
# - table aliases (c, s)
# - select aliases (total_profit)
# =========================================================
def extract_columns(ast):

    columns = set()

    # collect aliases first
    table_aliases = set()
    select_aliases = set()

    # -----------------------------------------------------
    # TABLE ALIASES
    # FROM customer c
    # JOIN sales s
    # -----------------------------------------------------
    for table in ast.find_all(exp.Table):

        if table.alias:
            table_aliases.add(
                table.alias.lower()
            )

    # -----------------------------------------------------
    # SELECT ALIASES
    # SUM(profit) AS total_profit
    # -----------------------------------------------------
    for alias in ast.find_all(exp.Alias):

        if alias.alias:
            select_aliases.add(
                alias.alias.lower()
            )

    # -----------------------------------------------------
    # REAL COLUMNS ONLY
    # -----------------------------------------------------
    for column in ast.find_all(exp.Column):

        column_name = column.name.lower()

        # skip table aliases
        if column_name in table_aliases:
            continue

        # skip select aliases
        if column_name in select_aliases:
            continue

        columns.add(column_name)

    return list(columns)


# =========================================================
# EXTRACT ALIASES
# Dynamic alias extraction across ALL SQL
# =========================================================
def extract_aliases(ast):

    aliases = set()

    # SELECT x AS alias
    for alias in ast.find_all(exp.Alias):

        if alias.alias:
            aliases.add(alias.alias.lower())

    return aliases


# =========================================================
# EXTRACT ORDER/GROUP REFERENCES
# Handles:
# ORDER BY total_profit
# GROUP BY order_month
# =========================================================
def extract_identifier_references(ast):

    identifiers = set()

    for node in ast.walk():

        # identifiers used in ORDER BY / GROUP BY
        if isinstance(node, exp.Identifier):

            if node.name:
                identifiers.add(node.name.lower())

    return identifiers


# =========================================================
# SEMANTIC PLACEHOLDER VALIDATION
# =========================================================
def validate_placeholder_mappings(sql: str, prompt: str):

    semantic_map = get_semantic_schema_map()

    sql_lower = sql.lower()
    prompt_lower = prompt.lower()

    for placeholder, semantic_type in PLACEHOLDER_TYPES.items():

        if placeholder.lower() not in prompt_lower:
            continue

        allowed_columns = [
            item["column"]
            for item in semantic_map.get(semantic_type, [])
        ]

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

    all_allowed_columns = set()

    for cols in allowed_columns_by_table.values():
        all_allowed_columns.update(cols)

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
    # EXTRACT TABLES & TABLE ALIASES
    # -----------------------------------------------------
    used_tables = extract_tables(ast)

    table_aliases = set()
    for table in ast.find_all(exp.Table):
        if table.alias:
            table_aliases.add(table.alias.lower())

    # -----------------------------------------------------
    # VALIDATE TABLES
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
    # EXTRACT VALID PHYSICAL COLUMNS
    # -----------------------------------------------------
    used_columns = extract_columns(ast)

    # -----------------------------------------------------
    # EXTRACT DYNAMIC ALIASES
    # -----------------------------------------------------
    aliases = extract_aliases(ast)

    # -----------------------------------------------------
    # EXTRACT IDENTIFIER REFERENCES
    # ORDER BY total_profit
    # GROUP BY order_month
    # etc
    # -----------------------------------------------------
    identifiers = extract_identifier_references(ast)

    # -----------------------------------------------------
    # REMOVE ALIASES FROM IDENTIFIER CHECK
    # -----------------------------------------------------
    identifiers = {
        item
        for item in identifiers
        if item not in aliases
    }

    # -----------------------------------------------------
    # COLUMN VALIDATION
    # ONLY REAL SCHEMA COLUMNS
    # -----------------------------------------------------
    invalid_columns = []

    for col in used_columns:

        if col.lower() not in all_allowed_columns:
            invalid_columns.append(col)

    # -----------------------------------------------------
    # IDENTIFIER VALIDATION
    # Ignore aliases and table aliases dynamically
    # -----------------------------------------------------
    for identifier in identifiers:

        if (
            identifier not in all_allowed_columns
            and identifier not in aliases
            and identifier not in used_tables
            and identifier not in table_aliases
        ):

            # ignore numeric GROUP BY refs
            if identifier.isdigit():
                continue

            invalid_columns.append(identifier)

    # remove duplicates
    invalid_columns = list(set(invalid_columns))

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
