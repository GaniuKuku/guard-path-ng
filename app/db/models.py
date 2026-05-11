from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Float,
    JSON,
    ForeignKey,
    Boolean
)

from sqlalchemy.orm import relationship

from datetime import datetime

from app.db.database import Base


class User(Base):

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    email = Column(String, unique=True, index=True, nullable=False)

    hashed_password = Column(String, nullable=False)

    role = Column(String, default="analyst")

    logs = relationship(
        "AuditLog",
        back_populates="user"
    )


class AuditLog(Base):

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)

    # =====================================================
    # USER RELATIONSHIP
    # =====================================================

    user_id = Column(
        Integer,
        ForeignKey("users.id")
    )

    user = relationship(
        "User",
        back_populates="logs"
    )

    # =====================================================
    # PROMPT DATA
    # =====================================================

    original_prompt = Column(Text)

    redacted_prompt = Column(Text)

    # =====================================================
    # PII SECURITY
    # =====================================================

    risk_score = Column(Float, default=0.0)

    risk_level = Column(String)

    detected_entities = Column(Text)

    entity_details = Column(JSON)

    # =====================================================
    # SQL FIREWALL AUDIT
    # =====================================================

    sql_allowed = Column(Boolean, default=True)

    sql_risks = Column(JSON)

    sql_decision_reason = Column(JSON)

    final_query = Column(Text)

    # =====================================================
    # TIMESTAMP
    # =====================================================

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )
