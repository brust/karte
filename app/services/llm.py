from __future__ import annotations

import json
import logging

from openai import OpenAI

from app.core.config import LITELLM_BASE_URL, LLM_MODEL, OPENAI_API_KEY

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are Karte, a helpful map assistant. You help users place and classify pins on a map.

Rules:
- If the user wants to add a place but hasn't provided coordinates, ask them to click on the map. \
Respond with EXACTLY the JSON action: {"action": "request_click"} at the END of your message, after your natural language response.
- When coordinates arrive (you'll see a system message with lat/lng), classify the location into \
one of these categories: school, health_clinic, bakery, supermarket, pharmacy, restaurant, cafe, bank, park, other.
- For classification, respond with a JSON block: {"action": "classify", "category": "<category>", "name": "<optional name guess>", "confidence": <0.0-1.0>, "reasoning": "<short explanation>"}
- Keep responses concise and friendly.
- Always respond in the same language the user is using.\
"""

PIN_CATEGORIES = [
    "school", "health_clinic", "bakery", "supermarket", "pharmacy",
    "restaurant", "cafe", "bank", "park", "other",
]

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            base_url=LITELLM_BASE_URL,
            api_key=OPENAI_API_KEY,
        )
    return _client


def get_assistant_response(history: list[dict]) -> dict:
    """Call the LLM and return parsed response.

    Returns dict with keys:
      - content: str (the assistant message text)
      - request_click: bool (whether the assistant wants a map click)
      - classification: dict | None (category, name, confidence, reasoning)
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=0.3,
        )
        content = response.choices[0].message.content or ""
    except Exception:
        logger.exception("LLM call failed")
        content = "Sorry, I'm having trouble connecting to my brain right now. Please try again."
        return {"content": content, "request_click": False, "classification": None}

    return _parse_response(content)


def _parse_response(content: str) -> dict:
    """Extract action JSON from the assistant's response."""
    result = {"content": content, "request_click": False, "classification": None}

    # Try to find JSON action block in the response
    try:
        # Find the last JSON object in the response
        last_brace = content.rfind("}")
        if last_brace == -1:
            return result

        first_brace = content.rfind("{", 0, last_brace)
        if first_brace == -1:
            return result

        json_str = content[first_brace : last_brace + 1]
        action_data = json.loads(json_str)

        action = action_data.get("action")
        if action == "request_click":
            result["request_click"] = True
            # Remove the JSON from the displayed content
            result["content"] = content[:first_brace].strip()
        elif action == "classify":
            result["classification"] = {
                "category": action_data.get("category", "other"),
                "name": action_data.get("name"),
                "confidence": action_data.get("confidence"),
                "reasoning": action_data.get("reasoning"),
            }
            result["content"] = content[:first_brace].strip()
    except (json.JSONDecodeError, ValueError):
        pass

    return result
