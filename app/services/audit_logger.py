from sqlalchemy.orm import Session

from app.db.models import AuditLog


def create_audit_log(
    db: Session,
    user_id: int,
    original_prompt: str,
    redacted_prompt: str,
    risk_score: float,
    risk_level: str,
    detected_entities: str,
    entity_details: list,

    # SQL FIREWALL
    sql_allowed: bool,
    sql_risks: list,
    sql_decision_reason: list,
    final_query: str = None
):

    log = AuditLog(
        user_id=user_id,

        original_prompt=original_prompt,
        redacted_prompt=redacted_prompt,

        risk_score=risk_score,
        risk_level=risk_level,

        detected_entities=detected_entities,
        entity_details=entity_details,

        sql_allowed=sql_allowed,
        sql_risks=sql_risks,
        sql_decision_reason=sql_decision_reason,
        final_query=final_query
    )

    db.add(log)

    db.commit()

    db.refresh(log)

    return log
