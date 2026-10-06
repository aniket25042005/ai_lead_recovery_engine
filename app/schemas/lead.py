from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class CustomerInfo(BaseModel):
    name: Optional[str] = Field(default=None, description="Name of the customer/prospect")
    phone: Optional[str] = Field(default=None, description="Phone number, e.g. +919876543210")


class LeadMetadata(BaseModel):
    source: Optional[str] = Field(default="whatsapp", description="Lead acquisition source")
    status: Optional[str] = Field(default="contacted", description="Current lead status")
    created_at: Optional[str] = Field(default=None, description="Creation timestamp or date string")
    last_contacted_at: Optional[str] = Field(default=None, description="Last contact timestamp or date string")


class ChatMessage(BaseModel):
    role: Literal["customer", "agent", "system"] = Field(..., description="Role of the sender")
    message: str = Field(..., min_length=1, description="Text content of the message")


class LeadAnalyzeRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1, description="Tenant identifier for multi-tenant isolation")
    lead_id: str = Field(..., min_length=1, description="Unique lead identifier")
    customer: Optional[CustomerInfo] = Field(default_factory=CustomerInfo)
    lead: Optional[LeadMetadata] = Field(default_factory=LeadMetadata)
    conversation: List[ChatMessage] = Field(..., min_length=1, description="Chronological conversation turns")

    model_config = {
        "json_schema_extra": {
            "example": {
                "tenant_id": "business_001",
                "lead_id": "lead_1024",
                "customer": {"name": "Arun Kumar", "phone": "+919876543210"},
                "lead": {
                    "source": "whatsapp",
                    "status": "contacted",
                    "created_at": "2026-09-20",
                    "last_contacted_at": "2026-09-25",
                },
                "conversation": [
                    {"role": "customer", "message": "I am interested in your CRM."},
                    {"role": "agent", "message": "How many users do you need?"},
                    {"role": "customer", "message": "Around 25 users. What is the pricing?"},
                ],
            }
        }
    }


class LeadRecoveryOutput(BaseModel):
    """Structured AI Recovery Output matching exact screening task requirements."""
    lead_score: int = Field(..., ge=0, le=100, description="Lead intent/priority score between 0 and 100")
    priority: Literal["high", "medium", "low"] = Field(..., description="Follow-up priority level")
    intent: str = Field(..., description="Primary identified intent, e.g., purchase, inquiry, opt_out")
    stage: str = Field(..., description="CRM pipeline stage, e.g., pricing_interest, discovery, lost")
    summary: str = Field(..., description="Concise synopsis of lead situation and conversation")
    next_best_action: str = Field(..., description="Actionable recommended next step for sales agent")
    follow_up_channel: Literal["whatsapp", "email", "sms", "call", "none"] = Field(
        default="whatsapp", description="Recommended channel for next touchpoint"
    )
    follow_up_message: Optional[str] = Field(
        default=None, description="Drafted personalized follow-up message (must be None if do_not_contact is True)"
    )
    do_not_contact: bool = Field(
        default=False, description="Flag indicating customer requested opt-out (STOP) or should not be contacted"
    )

    @field_validator("follow_up_message")
    @classmethod
    def validate_follow_up(cls, v, info):
        # Enforce that if do_not_contact is True, follow_up_message cannot be sent
        if info.data.get("do_not_contact") and v:
            return None
        return v


class FollowUpRequest(BaseModel):
    custom_instructions: Optional[str] = Field(
        default=None, description="Optional custom guidelines for tailoring the follow-up message"
    )


class FollowUpResponse(BaseModel):
    tenant_id: str
    lead_id: str
    follow_up_channel: str
    follow_up_message: Optional[str]
    do_not_contact: bool
    status: Literal["ready", "blocked_opt_out"]
    dispatched_mock: bool = Field(default=False, description="Simulated dispatch status via mock messaging provider")
