from sqlalchemy import inspect
from app.db.database import engine
from functools import lru_cache


# =========================================================
# INTERNAL TABLES (NEVER EXPOSED TO LLM)
# =========================================================
IGNORED_TABLES = {"users", "audit_logs"}


# =========================================================
# SEMANTIC COLUMN DETECTION
# Dynamic enterprise-safe classification
# =========================================================
SEMANTIC_PATTERNS = {
    "email": [
        "email",
        "mail"
    ],

    "phone": [
        "phone",
        "mobile",
        "telephone",
        "tel",
        "contact_number"
    ],

    "name": [
        "name",
        "fullname",
        "customer_name",
        "first_name",
        "last_name"
    ],

    "address": [
        "address",
        "street",
        "city",
        "state",
        "country",
        "postal"
    ],

    "id": [
        "id",
        "_id"
    ]
}


# =========================================================
# NORMALIZATION
# =========================================================
def _normalize(value: str) -> str:

    if not value:
        return ""

    return value.strip().lower()


# =========================================================
# SCHEMA EXTRACTION
# =========================================================
def _extract_schema(engine):

    inspector = inspect(engine)

    schema = {
        "tables": {}
    }

    for table_name in inspector.get_table_names():

        normalized_table = _normalize(table_name)

        # -------------------------------------------------
        # skip GuardPath internal tables
        # -------------------------------------------------
        if normalized_table in IGNORED_TABLES:
            continue

        columns = inspector.get_columns(table_name)

        pk = inspector.get_pk_constraint(table_name)

        fks = inspector.get_foreign_keys(table_name)

        schema["tables"][normalized_table] = {

            "original_name": table_name,

            "columns": [
                {
                    "name": _normalize(col["name"]),
                    "type": str(col["type"])
                }
                for col in columns
            ],

            "primary_key": (
                [
                    _normalize(pk_col)
                    for pk_col in pk.get(
                        "constrained_columns",
                        []
                    )
                ]
                if pk else []
            ),

            "foreign_keys": []
        }

        # =================================================
        # FOREIGN KEYS
        # =================================================
        if fks:

            for fk in fks:

                if (
                    fk.get("constrained_columns")
                    and fk.get("referred_table")
                ):

                    schema["tables"][normalized_table][
                        "foreign_keys"
                    ].append({

                        "from_column": _normalize(
                            fk["constrained_columns"][0]
                        ),

                        "to_table": _normalize(
                            fk["referred_table"]
                        ),

                        "to_column": _normalize(
                            fk["referred_columns"][0]
                        )
                    })

    return schema


# =========================================================
# CACHE
# =========================================================
@lru_cache(maxsize=1)
def get_schema_object():

    return _extract_schema(engine)


# =========================================================
# DYNAMIC SEMANTIC MAP
# Enterprise-safe semantic detection
# =========================================================
def build_semantic_map(schema):

    semantic_map = {}

    for semantic_type, patterns in SEMANTIC_PATTERNS.items():

        semantic_map[semantic_type] = []

        for table_name, meta in schema["tables"].items():

            for col in meta["columns"]:

                column_name = col["name"].lower()

                for pattern in patterns:

                    if pattern in column_name:

                        semantic_map[semantic_type].append({

                            "table": table_name,

                            "column": column_name
                        })

                        break

    return semantic_map


# =========================================================
# PUBLIC SEMANTIC MAP
# =========================================================
@lru_cache(maxsize=1)
def get_semantic_schema_map():

    schema = get_schema_object()

    return build_semantic_map(schema)


# =========================================================
# SCHEMA SCOPING
# =========================================================
def get_relevant_schema(user_query: str):

    schema = get_schema_object()

    query = _normalize(user_query)

    relevant_tables = set()

    # -----------------------------------------------------
    # direct table + column match
    # -----------------------------------------------------
    for table_name, table_meta in schema["tables"].items():

        if table_name in query:

            relevant_tables.add(table_name)

        for col in table_meta["columns"]:

            if col["name"] in query:

                relevant_tables.add(table_name)

    # -----------------------------------------------------
    # semantic expansion
    # -----------------------------------------------------
    semantic_map = get_semantic_schema_map()

    for semantic_type, mappings in semantic_map.items():

        if semantic_type in query:

            for item in mappings:

                relevant_tables.add(item["table"])

    # -----------------------------------------------------
    # relationship expansion
    # -----------------------------------------------------
    expanded = set(relevant_tables)

    for t in relevant_tables:

        if t not in schema["tables"]:
            continue

        for fk in schema["tables"][t]["foreign_keys"]:

            expanded.add(fk["to_table"])

    # =====================================================
    # SAFE FALLBACK
    # =====================================================
    if not expanded:

        return {
            "tables": {}
        }

    return {

        "tables": {

            t: schema["tables"][t]

            for t in sorted(expanded)

            if t in schema["tables"]
        }
    }


# =========================================================
# FORMAT FOR LLM
# =========================================================
def format_schema_for_llm(schema: dict) -> str:

    if not schema or not schema.get("tables"):

        return "EMPTY SCHEMA"

    output = []

    output.append(
        "DATABASE SCHEMA (STRICT RULES APPLY)"
    )

    output.append(
        "USE ONLY TABLES/COLUMNS BELOW.\n"
    )

    # deterministic ordering
    for table in sorted(schema["tables"].keys()):

        meta = schema["tables"][table]

        output.append(f"TABLE: {table}")

        columns = ", ".join([

            f"{c['name']} ({c['type']})"

            for c in meta["columns"]
        ])

        output.append(
            f"COLUMNS: {columns}"
        )

        if meta["primary_key"]:

            output.append(
                f"PRIMARY KEY: "
                f"{', '.join(meta['primary_key'])}"
            )

        if meta["foreign_keys"]:

            output.append("RELATIONSHIPS:")

            for fk in meta["foreign_keys"]:

                output.append(
                    f"  {table}.{fk['from_column']} -> "
                    f"{fk['to_table']}.{fk['to_column']}"
                )

        output.append("---")

    return "\n".join(output)


# =========================================================
# PUBLIC HELPERS
# =========================================================
def get_relevant_schema_text(user_query: str):

    return format_schema_for_llm(
        get_relevant_schema(user_query)
    )


def get_database_schema_text():

    return format_schema_for_llm(
        get_schema_object()
    )


def get_database_schema():

    return get_database_schema_text()


def get_schema_json():

    return get_schema_object()
