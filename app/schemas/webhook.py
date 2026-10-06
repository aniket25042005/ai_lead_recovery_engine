from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.lead import ChatMessage, CustomerInfo, LeadMetadata, LeadRecoveryOutput


class WebhookLeadPayload(BaseModel):
    event_id: Optional[str] = Field(default=None, description="Optional caller event identifier used for idempotency")
    idempotency_key: Optional[str] = Field(default=None, description="Optional caller idempotency key")
    tenant_id: str = Field(..., min_length=1, description="Tenant identifier")
    lead_id: str = Field(..., min_length=1, description="Lead identifier")
    customer: Optional[CustomerInfo] = Field(default_factory=CustomerInfo)
    lead: Optional[LeadMetadata] = Field(default_factory=LeadMetadata)
    conversation: List[ChatMessage] = Field(..., min_length=1)

    model_config = {
        "json_schema_extra": {
            "example": {
                "event_id": "evt_998822",
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


class WebhookResponse(BaseModel):
    status: str = Field(..., description="'accepted' or 'already_processed'")
    job_id: str
    idempotency_key: str
    message: str
    result: Optional[LeadRecoveryOutput] = Field(
        default=None, description="Immediately populated if already processed (idempotency)"
    )
