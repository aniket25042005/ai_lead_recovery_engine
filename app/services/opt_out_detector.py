import re
from typing import List
from app.schemas.lead import ChatMessage

OPT_OUT_PATTERNS = [
    r"\bstop\b",
    r"\bunsubscribe\b",
    r"\bcancel\b",
    r"\bend\b",
    r"\bquit\b",
    r"\bdo\s+not\s+(?:message|contact|call)\b",
    r"\bdon'?t\s+(?:message|contact|call)\b",
    r"\bleave\s+me\s+alone\b",
    r"\bnot\s+interested(?:\s+anymore)?\b",
    r"\bremove\s+(?:my\s+number|me)\b",
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in OPT_OUT_PATTERNS]


def detect_opt_out(conversation: List[ChatMessage]) -> bool:
    """
    Checks if any customer message in the conversation requests an opt-out.
    Enforces compliance with opt-out rules (e.g. TCPA, WhatsApp policy).
    """
    for msg in conversation:
        if msg.role == "customer":
            text = msg.message.strip()
            for pattern in COMPILED_PATTERNS:
                if pattern.search(text):
                    return True
    return False
