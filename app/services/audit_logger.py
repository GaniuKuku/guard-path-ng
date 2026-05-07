from sqlalchemy.orm import Session

from app.db.models import AuditLog


def create_audit_log(
    db: Session,
    original_prompt: str,
    redacted_prompt: str,
    risk_level: str,
    detected_entities: str
):

    log = AuditLog(
        original_prompt=original_prompt,
        redacted_prompt=redacted_prompt,
        risk_level=risk_level,
        detected_entities=detected_entities
    )

    db.add(log)

    db.commit()

    db.refresh(log)

    return log
