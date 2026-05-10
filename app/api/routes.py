from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from datetime import timedelta
from time import perf_counter

from app.schemas.prompt_schema import PromptRequest
from app.services.redactor import redact_sensitive_data
from app.services.sql_validator import validate_sql
from app.services.audit_logger import create_audit_log
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
# REQUEST SCHEMAS
# =========================================================

class UserCreate(BaseModel):
    email: EmailStr
    password: str

# =========================================================
# AUTHENTICATION ROUTES
# =========================================================

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_user(
    user: UserCreate,
    db: Session = Depends(get_db)
):
    normalized_email = user.email.strip().lower()

    existing_user = (
        db.query(User)
        .filter(User.email == normalized_email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    hashed_password = get_password_hash(user.password)

    new_user = User(
        email=normalized_email,
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
    normalized_email = form_data.username.strip().lower()

    user = (
        db.query(User)
        .filter(User.email == normalized_email)
        .first()
    )

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
        data={
            "sub": user.email,
            "user_id": user.id
        },
        expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

# =========================================================
# SCAN SERVICE ORCHESTRATION
# =========================================================

def process_scan(prompt: str):
    redaction_result = redact_sensitive_data(prompt)

    sql_risks = validate_sql(prompt)

    risk_score = redaction_result["risk_score"]
    risk_level = redaction_result["risk_level"]

    # SQL injection automatically escalates severity
    if sql_risks:
        risk_score = 1.0
        risk_level = "CRITICAL_SQL"

    return {
        **redaction_result,
        "sql_risks": sql_risks,
        "risk_score": risk_score,
        "risk_level": risk_level
    }

# =========================================================
# PROTECTED ROUTES
# =========================================================

@router.post("/scan")
def scan_prompt(
    request: PromptRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    start_time = perf_counter()

    result = process_scan(request.prompt)

    processing_time_ms = round(
        (perf_counter() - start_time) * 1000,
        2
    )

    # Persist audit log
    create_audit_log(
        db=db,
        user_id=current_user.id,
        original_prompt=result["original_prompt"],
        redacted_prompt=result["redacted_prompt"],
        risk_score=result["risk_score"],
        risk_level=result["risk_level"],
        detected_entities=result["detected_entities"],
        entity_details=result["entity_details"],
        sql_risks=result["sql_risks"]
    )

    return {
        **result,
        "scanned_by": current_user.email,
        "processing_time_ms": processing_time_ms
    }

@router.get("/me")
def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    return {
        "id": current_user.id,
        "email": current_user.email
    }

