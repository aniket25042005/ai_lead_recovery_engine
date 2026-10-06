import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List

logger = logging.getLogger("zizzet.messenger.whatsapp")


class MockWhatsAppMessenger:
    """
    Mock WhatsApp messaging provider fulfilling screening requirement:
    'A real WhatsApp API is not required; use a mock messaging provider/interface.'
    """

    def __init__(self):
        self._sent_messages: List[Dict[str, Any]] = []

    def send_message(
        self,
        to_phone: str,
        message: str,
        tenant_id: str,
        lead_id: str,
    ) -> Dict[str, Any]:
        message_id = f"wamid_{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now(timezone.utc).isoformat()
        
        receipt = {
            "message_id": message_id,
            "channel": "whatsapp",
            "to_phone": to_phone,
            "message": message,
            "tenant_id": tenant_id,
            "lead_id": lead_id,
            "status": "delivered",
            "timestamp": timestamp,
        }
        
        self._sent_messages.append(receipt)
        logger.info(
            "Mock WhatsApp message dispatched: [tenant=%s, lead=%s, to=%s, id=%s] '%s'",
            tenant_id, lead_id, to_phone, message_id, message[:40] + ("..." if len(message) > 40 else "")
        )
        return receipt

    def get_sent_messages(self) -> List[Dict[str, Any]]:
        return list(self._sent_messages)


mock_messenger = MockWhatsAppMessenger()
