from sqlalchemy.orm import Session
from app.db.models import AuditLog

# =========================================================
# AUDIT LOGGER SERVICE
# =========================================================

def create_audit_log(
    db: Session,
    user_id: int,
    original_prompt: str,
    redacted_prompt: str,
    risk_score: float,
    risk_level: str,
    detected_entities: list,
    entity_details: list,
    sql_risks: list = None
):
    """
    Creates an immutable audit log entry for GuardPath scans.
    Designed to be DB-agnostic and future scalable.
    """

    log = AuditLog(
        user_id=user_id,
        original_prompt=original_prompt,
        redacted_prompt=redacted_prompt,
        risk_score=risk_score,
        risk_level=risk_level,
        detected_entities=detected_entities,
        entity_details=entity_details,
        sql_risks=sql_risks or []
    )

    db.add(log)
    db.commit()
    db.refresh(log)

    return log
