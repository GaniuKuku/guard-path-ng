from app.services.sql_firewall.detector import looks_like_sql

from app.services.sql_firewall.analyzer import (
    parse_sql,
    find_risks
)

from app.services.sql_firewall.policies import (
    SQLPolicyEngine
)


policy_engine = SQLPolicyEngine()


def process_sql(prompt: str, role: str = "engineer"):

    # =====================================================
    # DEFAULT RESPONSE
    # =====================================================

    result = {
        "is_sql": False,
        "allowed": True,
        "risk_level": "LOW",
        "risks": [],
        "reason": [],
        "final_query": None
    }

    # =====================================================
    # SQL DETECTION
    # =====================================================

    if not looks_like_sql(prompt):
        return result

    result["is_sql"] = True

    # =====================================================
    # AST PARSING
    # =====================================================

    statements = parse_sql(prompt)

    # =====================================================
    # RISK ANALYSIS
    # =====================================================

    risks = find_risks(statements)

    result["risks"] = risks

    # =====================================================
    # POLICY EVALUATION
    # =====================================================

    decision = policy_engine.evaluate(
        risks=risks,
        query=prompt,
        role=role
    )

    result["allowed"] = decision["allowed"]

    result["risk_level"] = decision["risk_level"]

    result["reason"] = decision["reason"]

    # =====================================================
    # FINAL QUERY
    # =====================================================

    result["final_query"] = prompt if decision["allowed"] else None

    return result
