from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import timedelta
import time

from app.schemas.prompt_schema import PromptRequest
from app.services.redactor import redact_sensitive_data
from app.services.audit_logger import create_audit_log
from app.services.sql_firewall.engine import process_sql

from app.db.database import SessionLocal
from app.db.models import User

from app.services.auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

router = APIRouter()

# =========================================================
# DATABASE SESSION
# =========================================================

def get_db():
    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()

# =========================================================
# AUTH SCHEMAS
# =========================================================

class UserCreate(BaseModel):
    email: str
    password: str

# =========================================================
# AUTH ROUTES
# =========================================================

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_user(
    user: UserCreate,
    db: Session = Depends(get_db)
):
    existing_user = db.query(User).filter(
        User.email == user.email
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    hashed_password = get_password_hash(user.password)

    new_user = User(
        email=user.email,
        hashed_password=hashed_password
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": "User created successfully"
    }

@router.post("/login")
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(
        User.email == form_data.username
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(
        form_data.password,
        user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

# =========================================================
# CORE SCAN PROCESSOR
# =========================================================

def process_scan(prompt: str, role: str):

    # -----------------------------------------------------
    # 1. PII REDACTION
    # -----------------------------------------------------

    redaction_result = redact_sensitive_data(prompt)

    risk_score = redaction_result["risk_score"]

    risk_level = redaction_result["risk_level"]

    # -----------------------------------------------------
    # 2. SQL FIREWALL ENGINE
    # -----------------------------------------------------

    sql_result = process_sql(
        prompt=prompt,
        role=role
    )

    sql_risks = sql_result["risks"]

    final_query = sql_result.get("final_query")

    # -----------------------------------------------------
    # 3. SQL POLICY OVERRIDE
    # -----------------------------------------------------

    if not sql_result["allowed"]:
        risk_score = 1.0
        risk_level = "CRITICAL_SQL"

    # -----------------------------------------------------
    # 4. FINAL RESPONSE
    # -----------------------------------------------------

    return {
        **redaction_result,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "sql_risks": sql_risks,
        "sql_allowed": sql_result["allowed"],
        "sql_decision_reason": sql_result["reason"],
        "final_query": final_query
    }

# =========================================================
# PROTECTED SCAN ROUTE
# =========================================================

@router.post("/scan")
def scan_prompt(
    request: PromptRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    start_time = time.time()

    # -----------------------------------------------------
    # RUN SECURITY PIPELINE
    # -----------------------------------------------------

    result = process_scan(
        prompt=request.prompt,
        role=current_user.role
    )

    processing_time_ms = round(
        (time.time() - start_time) * 1000,
        2
    )

    # -----------------------------------------------------
    # AUDIT LOGGING
    # -----------------------------------------------------

    create_audit_log(
    db=db,

    user_id=current_user.id,

    original_prompt=result["original_prompt"],

    redacted_prompt=result["redacted_prompt"],

    risk_score=result["risk_score"],

    risk_level=result["risk_level"],

    detected_entities=", ".join(
        result["detected_entities"]
    ),

    entity_details=result["entity_details"],

    # =================================================
    # SQL FIREWALL AUDIT
    # =================================================

    sql_allowed=result["sql_allowed"],

    sql_risks=result["sql_risks"],

    sql_decision_reason=result["sql_decision_reason"],

    final_query=result.get("final_query")
)

    # -----------------------------------------------------
    # RESPONSE
    # -----------------------------------------------------

    result["scanned_by"] = current_user.email

    result["processing_time_ms"] = processing_time_ms

    return result
