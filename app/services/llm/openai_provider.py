import json
import logging
from tenacity import retry, stop_after_attempt, wait_exponential
from openai import OpenAI

from app.core.config import settings
from app.schemas.lead import LeadAnalyzeRequest, LeadRecoveryOutput
from app.services.llm.base import BaseLLMProvider
from app.services.llm.prompt_engine import SYSTEM_PROMPT, build_analysis_prompt
from app.services.opt_out_detector import detect_opt_out

logger = logging.getLogger("zizzet.llm.openai")


class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model or settings.OPENAI_MODEL
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not configured.")
        self.client = OpenAI(api_key=self.api_key)

    @retry(
        stop=stop_after_attempt(settings.LLM_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        reraise=True,
    )
    def _call_openai(self, prompt: str) -> str:
        logger.info("Calling OpenAI API with model=%s", self.model)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        return response.choices[0].message.content

    def analyze_lead(self, request: LeadAnalyzeRequest) -> LeadRecoveryOutput:
        # Pre-guardrail: Check opt out immediately
        is_opted_out = detect_opt_out(request.conversation)
        if is_opted_out:
            logger.info("Opt-out detected via pre-guardrail for lead %s", request.lead_id)
            return LeadRecoveryOutput(
                lead_score=10,
                priority="low",
                intent="opt_out",
                stage="lost",
                summary="Customer explicitly opted out of communications.",
                next_best_action="Mark lead as opted-out and do not contact",
                follow_up_channel="none",
                follow_up_message=None,
                do_not_contact=True,
            )

        prompt = build_analysis_prompt(request)
        raw_text = self._call_openai(prompt)

        try:
            parsed = json.loads(raw_text)
            output = LeadRecoveryOutput(**parsed)
            return output
        except Exception as exc:
            logger.error("Failed to parse OpenAI output: %s. Raw: %s", exc, raw_text)
            raise ValueError(f"Malformed LLM response from OpenAI: {exc}")
