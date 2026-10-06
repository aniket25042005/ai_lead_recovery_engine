import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_tenant_id, get_tenant_id_header
from app.schemas.lead import (
    LeadAnalyzeRequest,
    LeadRecoveryOutput,
    FollowUpRequest,
    FollowUpResponse,
)
from app.services.lead_service import LeadService

logger = logging.getLogger("zizzet.api.leads")
router = APIRouter()


@router.post(
    "/leads/analyze",
    response_model=LeadRecoveryOutput,
    status_code=status.HTTP_200_OK,
    summary="Analyze lead and conversation history",
    description="Synchronously analyzes a lead and conversation log with the LLM, returning a structured recovery recommendation.",
)
def analyze_lead(
    request: LeadAnalyzeRequest,
    db: Session = Depends(get_db),
    tenant_header: Optional[str] = Depends(get_tenant_id_header),
):
    # If header is provided, enforce that it matches the body's tenant_id
    if tenant_header and tenant_header != request.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mismatched Tenant: Header '{tenant_header}' does not match body tenant '{request.tenant_id}'",
        )

    try:
        result = LeadService.analyze_and_record_lead(db, request)
        return result
    except ValueError as exc:
        logger.error("Validation / LLM error analyzing lead: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except Exception as exc:
        logger.exception("Unexpected error during lead analysis: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing lead recovery analysis.",
        )


@router.get(
    "/leads/{lead_id}/analysis",
    response_model=LeadRecoveryOutput,
    status_code=status.HTTP_200_OK,
    summary="Retrieve latest analysis for a lead",
    description="Retrieves the most recent AI recovery recommendation for the specified lead. Enforces tenant isolation.",
)
def get_lead_analysis(
    lead_id: str,
    tenant_id: str = Depends(require_tenant_id),
    db: Session = Depends(get_db),
):
    analysis = LeadService.get_latest_analysis(db, tenant_id=tenant_id, lead_id=lead_id)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No analysis found for lead '{lead_id}' under tenant '{tenant_id}'.",
        )
    return analysis


@router.post(
    "/leads/{lead_id}/follow-up",
    response_model=FollowUpResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate personalized follow-up",
    description="Generates and dispatches a personalized follow-up message via mock WhatsApp. Blocks action if customer opted out.",
)
def generate_lead_follow_up(
    lead_id: str,
    payload: Optional[FollowUpRequest] = None,
    tenant_id: str = Depends(require_tenant_id),
    db: Session = Depends(get_db),
):
    custom_instructions = payload.custom_instructions if payload else None
    result = LeadService.generate_follow_up(
        db,
        tenant_id=tenant_id,
        lead_id=lead_id,
        custom_instructions=custom_instructions,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead '{lead_id}' not found under tenant '{tenant_id}'.",
        )
    return result
