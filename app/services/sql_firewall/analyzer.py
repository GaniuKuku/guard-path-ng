import sqlglot

from sqlglot import exp


# =========================================================
# SQL OPERATION GROUPS
# =========================================================

DESTRUCTIVE_NODES = (
    exp.Drop,
    exp.Alter,
)

WRITE_NODES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
)


# =========================================================
# SQL PARSER
# =========================================================

def parse_sql(prompt: str):

    try:
        return sqlglot.parse(
            prompt,
            read="postgres"
        )

    except Exception:
        return []


# =========================================================
# RISK DETECTOR
# =========================================================

def find_risks(statements):

    risks = []

    for stmt in statements:

        if not stmt:
            continue

        # -------------------------------------------------
        # UNSAFE MASS UPDATE / DELETE
        # -------------------------------------------------

        if isinstance(stmt, (exp.Update, exp.Delete)):

            if not stmt.args.get("where"):

                risks.append({
                    "category": "UNSAFE_MASS_OPERATION",
                    "operation": stmt.__class__.__name__,
                    "severity": "CRITICAL",
                    "reason": f"Unbounded {stmt.__class__.__name__.upper()} without WHERE clause"
                })

        # -------------------------------------------------
        # WALK AST TREE
        # -------------------------------------------------

        for node in stmt.walk():

            # ---------------------------------------------
            # DESTRUCTIVE
            # ---------------------------------------------

            if isinstance(node, DESTRUCTIVE_NODES):

                risks.append({
                    "category": "DESTRUCTIVE",
                    "operation": node.__class__.__name__,
                    "severity": "CRITICAL"
                })

            # ---------------------------------------------
            # WRITE OPERATIONS
            # ---------------------------------------------

            elif isinstance(node, WRITE_NODES):

                risks.append({
                    "category": "WRITE",
                    "operation": node.__class__.__name__,
                    "severity": "HIGH"
                })

    return risks
