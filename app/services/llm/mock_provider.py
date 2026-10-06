import re
from typing import Optional
from app.schemas.lead import LeadAnalyzeRequest, LeadRecoveryOutput
from app.services.llm.base import BaseLLMProvider
from app.services.opt_out_detector import detect_opt_out


class MockLLMProvider(BaseLLMProvider):
    """
    Intelligent deterministic provider for testing and offline evaluation.
    Reliably simulates LLM behavior across all evaluation cases (A, B, C, D)
    and general lead conversations.
    """

    def analyze_lead(self, request: LeadAnalyzeRequest) -> LeadRecoveryOutput:
        customer_name = request.customer.name if request.customer and request.customer.name else "there"
        customer_msgs = [m.message for m in request.conversation if m.role == "customer"]
        full_text = " ".join(customer_msgs)
        full_text_lower = full_text.lower()

        # Check for opt-out (Case D)
        if detect_opt_out(request.conversation):
            return LeadRecoveryOutput(
                lead_score=10,
                priority="low",
                intent="opt_out",
                stage="lost",
                summary=f"Customer {customer_name} explicitly opted out of communications.",
                next_best_action="Mark lead as opted-out and do not contact",
                follow_up_channel="none",
                follow_up_message=None,
                do_not_contact=True,
            )

        # Check for Demo / Call request (Case C)
        if any(term in full_text_lower for term in ["demo", "schedule a call", "call tomorrow", "meeting", "call me"]):
            return LeadRecoveryOutput(
                lead_score=90,
                priority="high",
                intent="demo_request",
                stage="demo_requested",
                summary=f"Customer {customer_name} requested a product demo/call.",
                next_best_action="Schedule a product demo and send meeting invite for tomorrow",
                follow_up_channel="whatsapp",
                follow_up_message=f"Hi {customer_name}! I would be happy to schedule a demo for tomorrow. What time works best for you?",
                do_not_contact=False,
            )

        # Check for Team Size / High Intent / Pricing (Case A and Example input)
        # E.g. "50 employees", "25 users", "pricing"
        has_pricing = any(term in full_text_lower for term in ["pricing", "cost", "quote", "rate", "price", "how much"])
        team_size_match = re.search(r"(\d+)\s*(?:employees|users|members|people|seats)", full_text_lower)

        if team_size_match or (has_pricing and any(num in full_text_lower for num in ["50", "25", "10", "100"])):
            size = team_size_match.group(1) if team_size_match else "team"
            return LeadRecoveryOutput(
                lead_score=86,
                priority="high",
                intent="purchase",
                stage="pricing_interest",
                summary=f"Customer is evaluating CRM pricing for a {size}-member team.",
                next_best_action="Send pricing and schedule a demo",
                follow_up_channel="whatsapp",
                follow_up_message=f"Hi {customer_name}! Just following up on your CRM requirement for your team. Here is our pricing breakdown, and I'd love to walk you through a quick demo.",
                do_not_contact=False,
            )

        # Check for low-priority / vague questions (Case B)
        # E.g. "Only asks what the product does"
        if any(term in full_text_lower for term in ["what does the product do", "what is this", "what do you do", "tell me more"]):
            return LeadRecoveryOutput(
                lead_score=35,
                priority="low",
                intent="inquiry",
                stage="discovery",
                summary=f"Customer {customer_name} made an initial high-level inquiry about product capabilities.",
                next_best_action="Send introductory product overview brochure",
                follow_up_channel="whatsapp",
                follow_up_message=f"Hi {customer_name}! Thanks for reaching out. In short, our platform helps automate your sales workflow and recover lost leads. Would you like a brief overview document?",
                do_not_contact=False,
            )

        # Default fallback analysis for general leads
        return LeadRecoveryOutput(
            lead_score=50,
            priority="medium",
            intent="inquiry",
            stage="evaluation",
            summary=f"Customer {customer_name} expressed general interest in the product.",
            next_best_action="Follow up to assess business requirements",
            follow_up_channel="whatsapp",
            follow_up_message=f"Hi {customer_name}! Just checking in to see if you have any questions regarding our solutions.",
            do_not_contact=False,
        )
