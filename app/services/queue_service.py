import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Tuple, Optional
from sqlalchemy.orm import Session

from app.db.models import WebhookEvent
from app.db.session import SessionLocal
from app.schemas.lead import LeadAnalyzeRequest, LeadRecoveryOutput
from app.schemas.webhook import WebhookLeadPayload
from app.services.lead_service import LeadService

logger = logging.getLogger("zizzet.queue")


class QueueService:
    @staticmethod
    def generate_idempotency_key(payload: WebhookLeadPayload, explicit_key: Optional[str] = None) -> str:
        """
        Derives idempotency key from header/payload or deterministic hash of contents.
        """
        if explicit_key:
            return explicit_key
        if payload.idempotency_key:
            return payload.idempotency_key
        if payload.event_id:
            return payload.event_id

        # Deterministic SHA256 of tenant, lead, and conversation messages
        unique_repr = f"{payload.tenant_id}:{payload.lead_id}:" + ":".join(
            f"{m.role}:{m.message}" for m in payload.conversation
        )
        return hashlib.sha256(unique_repr.encode("utf-8")).hexdigest()

    @classmethod
    def register_event(
        cls,
        db: Session,
        payload: WebhookLeadPayload,
        explicit_key: Optional[str] = None,
    ) -> Tuple[WebhookEvent, bool]:
        """
        Registers event in idempotency table.
        Returns (WebhookEvent, is_new).
        If already exists, is_new=False (duplicate detected).
        """
        idempotency_key = cls.generate_idempotency_key(payload, explicit_key)

        existing = (
            db.query(WebhookEvent)
            .filter(
                WebhookEvent.tenant_id == payload.tenant_id,
                WebhookEvent.idempotency_key == idempotency_key,
            )
            .first()
        )

        if existing:
            logger.info(
                "Idempotency hit: Webhook event '%s' for tenant '%s' already exists (status=%s)",
                idempotency_key,
                payload.tenant_id,
                existing.status,
            )
            return existing, False

        # Create new record
        event = WebhookEvent(
            tenant_id=payload.tenant_id,
            idempotency_key=idempotency_key,
            event_type="lead_event",
            payload=payload.model_dump_json(),
            status="received",
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event, True

    @classmethod
    def process_webhook_task(cls, event_id: str):
        """
        Background task executed asynchronously by the worker.
        """
        db = SessionLocal()
        try:
            event = db.query(WebhookEvent).filter(WebhookEvent.id == event_id).first()
            if not event:
                logger.error("Background job failed: Event %s not found in DB", event_id)
                return

            if event.status == "completed":
                logger.info("Event %s already completed. Skipping.", event_id)
                return

            event.status = "processing"
            db.commit()

            data = json.loads(event.payload)
            lead_request = LeadAnalyzeRequest(**data)

            # Perform AI Lead Recovery Analysis
            result = LeadService.analyze_and_record_lead(db, lead_request)

            event.status = "completed"
            event.result = result.model_dump_json()
            event.completed_at = datetime.now(timezone.utc)
            db.commit()

            logger.info("Background job successfully processed event %s for tenant %s", event_id, event.tenant_id)
        except Exception as exc:
            logger.exception("Error processing background webhook event %s: %s", event_id, exc)
            db.rollback()
            try:
                event = db.query(WebhookEvent).filter(WebhookEvent.id == event_id).first()
                if event:
                    event.status = "failed"
                    event.error = str(exc)
                    db.commit()
            except Exception:
                pass
        finally:
            db.close()
