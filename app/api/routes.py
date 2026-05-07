from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.schemas.prompt_schema import PromptRequest

from app.services.redactor import redact_sensitive_data
from app.services.sql_validator import validate_sql
from app.services.audit_logger import create_audit_log

from app.db.database import SessionLocal

router = APIRouter()


def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


@router.post("/scan")

def scan_prompt(
    request: PromptRequest,
    db: Session = Depends(get_db)
):

    original_prompt = request.prompt

    redacted_prompt, detected = redact_sensitive_data(
        original_prompt
    )

    sql_risks = validate_sql(original_prompt)

    risk_level = "LOW"

    if detected or sql_risks:
        risk_level = "HIGH"

    create_audit_log(
        db=db,
        original_prompt=original_prompt,
        redacted_prompt=redacted_prompt,
        risk_level=risk_level,
        detected_entities=", ".join(detected)
    )

    return {
        "original_prompt": original_prompt,
        "redacted_prompt": redacted_prompt,
        "detected_entities": detected,
        "sql_risks": sql_risks,
        "risk_level": risk_level
    }
