import json
import logging
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.lead import LeadRecoveryOutput
from app.schemas.webhook import WebhookLeadPayload, WebhookResponse
from app.services.queue_service import QueueService

logger = logging.getLogger("zizzet.api.webhooks")
router = APIRouter()


@router.post(
    "/webhooks/leads",
    response_model=WebhookResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Receive lead event via webhook",
    description="Receives incoming lead webhook events, enforces idempotency, and enqueues background AI processing.",
)
def handle_lead_webhook(
    payload: WebhookLeadPayload,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    try:
        event, is_new = QueueService.register_event(
            db=db,
            payload=payload,
            explicit_key=x_idempotency_key,
        )

        # Idempotency: duplicate webhook event submitted
        if not is_new:
            result_obj = None
            if event.result:
                try:
                    result_obj = LeadRecoveryOutput(**json.loads(event.result))
                except Exception:
                    pass

            return WebhookResponse(
                status="already_processed" if event.status == "completed" else "already_processing",
                job_id=event.id,
                idempotency_key=event.idempotency_key,
                message=f"Duplicate event detected. Event status is '{event.status}'. No new job queued.",
                result=result_obj,
            )

        # New event: trigger background worker task
        background_tasks.add_task(QueueService.process_webhook_task, event.id)

        return WebhookResponse(
            status="accepted",
            job_id=event.id,
            idempotency_key=event.idempotency_key,
            message="Lead webhook event accepted for asynchronous background processing.",
            result=None,
        )
    except Exception as exc:
        logger.exception("Failed to process webhook event: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register webhook event.",
        )
