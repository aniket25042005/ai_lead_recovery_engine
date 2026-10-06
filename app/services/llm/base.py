from abc import ABC, abstractmethod
from app.schemas.lead import LeadAnalyzeRequest, LeadRecoveryOutput


class BaseLLMProvider(ABC):
    """Abstract Base Class for LLM providers."""

    @abstractmethod
    def analyze_lead(self, request: LeadAnalyzeRequest) -> LeadRecoveryOutput:
        """
        Analyzes a lead profile and conversation history, returning
        a validated structured LeadRecoveryOutput.
        """
        pass
