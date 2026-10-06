import json
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.models import Tenant, Lead, Conversation, LeadAnalysis
from app.schemas.lead import (
    LeadAnalyzeRequest,
    LeadRecoveryOutput,
    FollowUpResponse,
)
from app.services.opt_out_detector import detect_opt_out
from app.services.llm.factory import get_llm_provider
from app.services.messenger import mock_messenger

logger = logging.getLogger("zizzet.lead_service")


class LeadService:
    @staticmethod
    def _ensure_tenant(db: Session, tenant_id: str) -> Tenant:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            tenant = Tenant(id=tenant_id, name=f"Tenant {tenant_id}")
            db.add(tenant)
            db.flush()
        return tenant

    @classmethod
    def analyze_and_record_lead(
        cls, db: Session, request: LeadAnalyzeRequest
    ) -> LeadRecoveryOutput:
        """
        Ingests lead and conversation history, runs LLM recovery analysis,
        and persists lead, conversations, and structured analysis.
        Strictly enforces tenant isolation and opt-out rules.
        """
        cls._ensure_tenant(db, request.tenant_id)

        # 1. Check Opt-Out Rule
        is_opted_out = detect_opt_out(request.conversation)

        # 2. Upsert Lead
        lead = (
            db.query(Lead)
            .filter(Lead.tenant_id == request.tenant_id, Lead.id == request.lead_id)
            .first()
        )
        if not lead:
            lead = Lead(
                id=request.lead_id,
                tenant_id=request.tenant_id,
                customer_name=request.customer.name if request.customer else None,
                customer_phone=request.customer.phone if request.customer else None,
                source=request.lead.source if request.lead else "whatsapp",
                status=request.lead.status if request.lead else "contacted",
                do_not_contact=is_opted_out,
            )
            db.add(lead)
            db.flush()
        else:
            if request.customer and request.customer.name:
                lead.customer_name = request.customer.name
            if request.customer and request.customer.phone:
                lead.customer_phone = request.customer.phone
            if is_opted_out:
                lead.do_not_contact = True

        # 3. Save Conversation Messages
        for msg in request.conversation:
            convo_record = Conversation(
                tenant_id=request.tenant_id,
                lead_id=request.lead_id,
                role=msg.role,
                message=msg.message,
            )
            db.add(convo_record)
        db.flush()

        # 4. Invoke LLM Provider
        provider = get_llm_provider()
        analysis_result = provider.analyze_lead(request)

        # Guardrail enforcement: If customer opted out, do_not_contact must be true & no follow up
        if is_opted_out or analysis_result.do_not_contact:
            analysis_result.do_not_contact = True
            analysis_result.follow_up_message = None
            lead.do_not_contact = True

        # 5. Persist Analysis Record
        analysis_record = LeadAnalysis(
            tenant_id=request.tenant_id,
            lead_id=request.lead_id,
            lead_score=analysis_result.lead_score,
            priority=analysis_result.priority,
            intent=analysis_result.intent,
            stage=analysis_result.stage,
            summary=analysis_result.summary,
            next_best_action=analysis_result.next_best_action,
            follow_up_channel=analysis_result.follow_up_channel,
            follow_up_message=analysis_result.follow_up_message,
            do_not_contact=analysis_result.do_not_contact,
            raw_llm_response=json.dumps(analysis_result.model_dump()),
        )
        db.add(analysis_record)
        db.commit()

        logger.info(
            "Analyzed lead [tenant=%s, lead=%s]: score=%d, priority=%s, opt_out=%s",
            request.tenant_id,
            request.lead_id,
            analysis_result.lead_score,
            analysis_result.priority,
            analysis_result.do_not_contact,
        )

        return analysis_result

    @classmethod
    def get_latest_analysis(
        cls, db: Session, tenant_id: str, lead_id: str
    ) -> Optional[LeadRecoveryOutput]:
        """
        Retrieves latest analysis ensuring tenant isolation.
        Returns None if lead does not belong to tenant.
        """
        record = (
            db.query(LeadAnalysis)
            .filter(
                LeadAnalysis.tenant_id == tenant_id,
                LeadAnalysis.lead_id == lead_id,
            )
            .order_by(desc(LeadAnalysis.created_at))
            .first()
        )
        if not record:
            return None

        return LeadRecoveryOutput(
            lead_score=record.lead_score,
            priority=record.priority,
            intent=record.intent,
            stage=record.stage,
            summary=record.summary,
            next_best_action=record.next_best_action,
            follow_up_channel=record.follow_up_channel,
            follow_up_message=record.follow_up_message,
            do_not_contact=record.do_not_contact,
        )

    @classmethod
    def generate_follow_up(
        cls,
        db: Session,
        tenant_id: str,
        lead_id: str,
        custom_instructions: Optional[str] = None,
    ) -> Optional[FollowUpResponse]:
        """
        Generates/retrieves follow-up for a lead.
        Blocks and sets status='blocked_opt_out' if customer opted out (do_not_contact=true).
        Simulates dispatch via Mock WhatsApp provider if allowed.
        """
        lead = (
            db.query(Lead)
            .filter(Lead.tenant_id == tenant_id, Lead.id == lead_id)
            .first()
        )
        if not lead:
            return None

        # Check if customer opted out
        if lead.do_not_contact:
            logger.warning(
                "Follow-up blocked for lead %s: customer opted out (do_not_contact=True)",
                lead_id,
            )
            return FollowUpResponse(
                tenant_id=tenant_id,
                lead_id=lead_id,
                follow_up_channel="none",
                follow_up_message=None,
                do_not_contact=True,
                status="blocked_opt_out",
                dispatched_mock=False,
            )

        # Retrieve latest analysis
        analysis = cls.get_latest_analysis(db, tenant_id, lead_id)
        if not analysis:
            follow_up_message = (
                f"Hi {lead.customer_name or 'there'}! Following up on your recent inquiry."
            )
            channel = "whatsapp"
        else:
            follow_up_message = analysis.follow_up_message
            channel = analysis.follow_up_channel

        if custom_instructions and follow_up_message:
            follow_up_message += f" Note: {custom_instructions}"

        # Dispatch via mock WhatsApp if channel is whatsapp and phone is present
        dispatched = False
        if follow_up_message and channel == "whatsapp":
            phone = lead.customer_phone or "+1000000000"
            mock_messenger.send_message(
                to_phone=phone,
                message=follow_up_message,
                tenant_id=tenant_id,
                lead_id=lead_id,
            )
            dispatched = True

        return FollowUpResponse(
            tenant_id=tenant_id,
            lead_id=lead_id,
            follow_up_channel=channel,
            follow_up_message=follow_up_message,
            do_not_contact=False,
            status="ready",
            dispatched_mock=dispatched,
        )
