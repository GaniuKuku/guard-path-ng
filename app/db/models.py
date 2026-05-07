from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime

from app.db.database import Base


class AuditLog(Base):

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)

    original_prompt = Column(Text)

    redacted_prompt = Column(Text)

    risk_level = Column(String)

    detected_entities = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)
