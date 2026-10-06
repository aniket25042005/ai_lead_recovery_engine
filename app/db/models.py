import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now())

    leads = relationship("Lead", back_populates="tenant", cascade="all, delete-orphan")


class Lead(Base):
    __tablename__ = "leads"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_name = Column(String(255), nullable=True)
    customer_phone = Column(String(64), nullable=True)
    source = Column(String(64), nullable=True, default="whatsapp")
    status = Column(String(64), nullable=True, default="contacted")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now())
    last_contacted_at = Column(DateTime(timezone=True), nullable=True)
    do_not_contact = Column(Boolean, default=False, nullable=False)

    tenant = relationship("Tenant", back_populates="leads")
    conversations = relationship("Conversation", back_populates="lead", cascade="all, delete-orphan")
    analyses = relationship("LeadAnalysis", back_populates="lead", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_leads_tenant_id_id", "tenant_id", "id"),
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(String(64), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(32), nullable=False)  # "customer", "agent", "system"
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now())

    lead = relationship("Lead", back_populates="conversations")

    __table_args__ = (
        Index("ix_conversations_tenant_lead", "tenant_id", "lead_id"),
    )


class LeadAnalysis(Base):
    __tablename__ = "lead_analyses"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(String(64), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_score = Column(Integer, nullable=False)
    priority = Column(String(16), nullable=False)  # "high", "medium", "low"
    intent = Column(String(64), nullable=False)
    stage = Column(String(64), nullable=False)
    summary = Column(Text, nullable=False)
    next_best_action = Column(Text, nullable=False)
    follow_up_channel = Column(String(32), nullable=False, default="whatsapp")
    follow_up_message = Column(Text, nullable=True)
    do_not_contact = Column(Boolean, default=False, nullable=False)
    raw_llm_response = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now())

    lead = relationship("Lead", back_populates="analyses")

    __table_args__ = (
        Index("ix_lead_analyses_tenant_lead", "tenant_id", "lead_id"),
    )


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(64), nullable=False, index=True)
    idempotency_key = Column(String(128), nullable=False, index=True)
    event_type = Column(String(64), default="lead_event", nullable=False)
    payload = Column(Text, nullable=False)
    status = Column(String(32), default="received", nullable=False)  # "received", "processing", "completed", "failed"
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_webhook_tenant_idempotency"),
    )
