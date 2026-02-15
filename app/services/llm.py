from __future__ import annotations

import json
import logging

from openai import OpenAI

from app.core import config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are Karte, a helpful map assistant. You help users place and classify pins on a map.

Available categories: school, health_clinic, bakery, supermarket, pharmacy, restaurant, cafe, bank, park, other.

Actions — append EXACTLY ONE JSON block at the END of your message when needed:

1. **Place a pin by address/name**: When the user mentions a place, address, or landmark, place it directly:
   {"action": "place_pin", "address": "<address or place name to geocode>", "category": "<category>", "name": "<place name>", "confidence": <0.0-1.0>}

2. **Request a map click**: ONLY if the user wants to add a place but gives NO identifiable address or name:
   {"action": "request_click"}

3. **Classify coordinates**: When coordinates arrive (system message with lat/lng):
   {"action": "classify", "category": "<category>", "name": "<optional name guess>", "confidence": <0.0-1.0>, "reasoning": "<short explanation>"}

Rules:
- PREFER place_pin whenever possible. Use request_click only as a last resort when no location can be determined.
- For place_pin, use the most specific address you can build from what the user said (include city/country if mentioned or inferable from context).
- Keep responses concise and friendly.
- Always respond in the same language the user is using.\
"""

PIN_CATEGORIES = [
    "school", "health_clinic", "bakery", "supermarket", "pharmacy",
    "restaurant", "cafe", "bank", "park", "other",
]

def _get_client() -> OpenAI:
    return OpenAI(
        base_url=config.LITELLM_BASE_URL,
        api_key=config.OPENAI_API_KEY,
    )


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
            model=config.LLM_MODEL,
            messages=messages,
            temperature=0.3,
        )
        content = response.choices[0].message.content or ""
    except Exception:
        logger.exception("LLM call failed")
        content = "Sorry, I'm having trouble connecting to my brain right now. Please try again."
        return {"content": content, "request_click": False, "classification": None, "place_pin": None}

    return _parse_response(content)


def _parse_response(content: str) -> dict:
    """Extract action JSON from the assistant's response."""
    result = {"content": content, "request_click": False, "classification": None, "place_pin": None}

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
        if action == "place_pin":
            result["place_pin"] = {
                "address": action_data.get("address", ""),
                "category": action_data.get("category", "other"),
                "name": action_data.get("name"),
                "confidence": action_data.get("confidence"),
            }
            result["content"] = content[:first_brace].strip()
        elif action == "request_click":
            result["request_click"] = True
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
