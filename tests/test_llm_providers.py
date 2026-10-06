import pytest
from unittest.mock import MagicMock, patch
from app.schemas.lead import ChatMessage, LeadAnalyzeRequest, CustomerInfo, LeadMetadata
from app.services.llm.mock_provider import MockLLMProvider
from app.services.llm.gemini_provider import GeminiProvider
from app.services.llm.openai_provider import OpenAIProvider
from app.services.llm.factory import get_llm_provider
from app.core.config import settings


def sample_request(message="Interested in the product for 50 users."):
    return LeadAnalyzeRequest(
        tenant_id="test_tenant",
        lead_id="test_lead",
        customer=CustomerInfo(name="Test User", phone="+123456789"),
        lead=LeadMetadata(source="whatsapp", status="contacted"),
        conversation=[ChatMessage(role="customer", message=message)],
    )


def test_mock_llm_provider_behavior():
    provider = MockLLMProvider()
    res = provider.analyze_lead(sample_request("50 employees, what is pricing?"))
    assert res.priority == "high"
    assert res.intent == "purchase"
    assert res.do_not_contact is False

    res_opt_out = provider.analyze_lead(sample_request("Please STOP messaging me"))
    assert res_opt_out.do_not_contact is True
    assert res_opt_out.follow_up_message is None


def test_gemini_provider_malformed_response_handling():
    with patch("app.services.llm.gemini_provider.genai.Client") as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        # Simulate malformed output from LLM
        mock_response = MagicMock()
        mock_response.text = "NOT_A_JSON_STRING"
        mock_instance.models.generate_content.return_value = mock_response

        provider = GeminiProvider(api_key="fake-test-key", model="gemini-2.5-flash")
        with pytest.raises(ValueError, match="Malformed LLM response"):
            provider.analyze_lead(sample_request())


def test_openai_provider_malformed_response_handling():
    with patch("app.services.llm.openai_provider.OpenAI") as mock_openai:
        mock_instance = MagicMock()
        mock_openai.return_value = mock_instance
        mock_choice = MagicMock()
        mock_choice.message.content = "INVALID_JSON"
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_instance.chat.completions.create.return_value = mock_resp

        provider = OpenAIProvider(api_key="fake-test-key", model="gpt-4o-mini")
        with pytest.raises(ValueError, match="Malformed LLM response"):
            provider.analyze_lead(sample_request())


def test_llm_factory_selection(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "mock")
    prov = get_llm_provider()
    assert isinstance(prov, MockLLMProvider)
