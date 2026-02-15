from __future__ import annotations

import json
import logging
import re

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

4. **Delete pins**: When the user asks to remove, delete, or clear pins:
   {"action": "delete_pins", "which": "all"} — to delete ALL pins
   {"action": "delete_pins", "which": "drafts"} — to delete only draft pins
   {"action": "delete_pins", "which": "named", "names": ["name1", "name2"]} — to delete specific pins by name

5. **List pins**: When the user asks to list, show, or see all pins:
   {"action": "list_pins"}

Rules:
- Use actions for pin operations: ADD, REMOVE, CLASSIFY, or LIST. For counting, general questions, or conversation, respond with plain text and NO JSON action block.
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


def _build_map_state_message(pins: list[dict]) -> str:
    """Build a system message describing the current map state."""
    if not pins:
        return "Current map state: The map has no pins yet."

    confirmed = [p for p in pins if p.get("status") == "confirmed"]
    drafts = [p for p in pins if p.get("status") == "draft"]

    lines = [f"Current map state: {len(pins)} pin(s) total ({len(confirmed)} confirmed, {len(drafts)} draft)."]
    for p in pins:
        name = p.get("name") or "unnamed"
        cat = p.get("category", "other").replace("_", " ")
        status = p.get("status", "unknown")
        lines.append(f"- [{status}] {name} ({cat}) at ({p['lat']:.5f}, {p['lng']:.5f})")

    return "\n".join(lines)


def get_assistant_response(history: list[dict], pins: list[dict] | None = None) -> dict:
    """Call the LLM and return parsed response.

    Returns dict with keys:
      - content: str (the assistant message text)
      - request_click: bool (whether the assistant wants a map click)
      - classification: dict | None (category, name, confidence, reasoning)
      - place_pin: dict | None (address, category, name, confidence)
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if pins is not None:
        messages.append({"role": "system", "content": _build_map_state_message(pins)})
    messages.extend(history)

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
        return {"content": content, "request_click": False, "classification": None, "place_pin": None, "delete_pins": None}

    return _parse_response(content)


def _parse_response(content: str) -> dict:
    """Extract action JSON from the assistant's response."""
    result = {"content": content, "request_click": False, "classification": None, "place_pin": None, "delete_pins": None, "list_pins": False}

    # Try to find JSON action block in the response
    try:
        # Strip markdown code fences wrapping JSON (```json ... ``` or ``` ... ```)
        stripped = re.sub(r"```(?:json)?\s*(\{.*?\})\s*```", r"\1", content, flags=re.DOTALL)

        # Find the last JSON object in the response
        last_brace = stripped.rfind("}")
        if last_brace == -1:
            return result

        first_brace = stripped.rfind("{", 0, last_brace)
        if first_brace == -1:
            return result

        json_str = stripped[first_brace : last_brace + 1]
        action_data = json.loads(json_str)

        # Use stripped version for content cleaning
        content = stripped

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
        elif action == "delete_pins":
            result["delete_pins"] = {
                "which": action_data.get("which", "all"),
                "names": action_data.get("names", []),
            }
            result["content"] = content[:first_brace].strip()
        elif action == "list_pins":
            result["list_pins"] = True
            result["content"] = content[:first_brace].strip()
    except (json.JSONDecodeError, ValueError):
        pass

    return result
