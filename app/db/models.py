from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Float,
    JSON,
    ForeignKey
)

from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.database import Base

# =========================================================
# USER MODEL
# =========================================================

class User(Base):
    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    email = Column(
        String,
        unique=True,
        index=True,
        nullable=False
    )

    hashed_password = Column(
        String,
        nullable=False
    )

    role = Column(
        String,
        default="engineer",
        nullable=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # Relationship to audit logs
    logs = relationship(
        "AuditLog",
        back_populates="user",
        cascade="all, delete-orphan"
    )

# =========================================================
# AUDIT LOG MODEL
# =========================================================

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    original_prompt = Column(
        Text,
        nullable=False
    )

    redacted_prompt = Column(
        Text,
        nullable=False
    )

    risk_score = Column(
        Float,
        default=0.0,
        nullable=False
    )

    risk_level = Column(
        String,
        nullable=False
    )

    detected_entities = Column(
        JSON,
        default=list,
        nullable=False
    )

    entity_details = Column(
        JSON,
        default=list,
        nullable=False
    )

    sql_risks = Column(
        JSON,
        default=list,
        nullable=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )

    # Relationship back to user
    user = relationship(
        "User",
        back_populates="logs"
    )
