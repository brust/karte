from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.llm import _parse_response, get_chat_model


def test_parse_request_click():
    content = 'Sure, please click on the map! {"action": "request_click"}'
    result = _parse_response(content)
    assert result["request_click"] is True
    assert result["content"] == "Sure, please click on the map!"


def test_parse_classify():
    content = (
        'I think this is a bakery. '
        '{"action": "classify", "category": "bakery", "name": "Corner Bakery", '
        '"confidence": 0.85, "reasoning": "Located in commercial area"}'
    )
    result = _parse_response(content)
    assert result["classification"]["category"] == "bakery"
    assert result["classification"]["name"] == "Corner Bakery"
    assert result["classification"]["confidence"] == 0.85
    assert result["content"] == "I think this is a bakery."


def test_parse_no_action():
    content = "Just a regular message without any action."
    result = _parse_response(content)
    assert result["request_click"] is False
    assert result["classification"] is None
    assert result["content"] == content


def test_parse_invalid_json():
    content = "Here is some text with {broken json"
    result = _parse_response(content)
    assert result["request_click"] is False
    assert result["classification"] is None


def test_parse_json_in_code_fence():
    content = 'Here are your pins:\n\n```json\n{"action": "list_pins"}\n```'
    result = _parse_response(content)
    assert result["list_pins"] is True
    assert "json" not in result["content"]
    assert "```" not in result["content"]


def test_parse_json_with_trailing_json_label():
    content = 'I\'ll place that for you.\n\njson\n{"action": "place_pin", "address": "Paulista Ave", "category": "bakery", "name": "Test", "confidence": 0.9}'
    result = _parse_response(content)
    assert result["place_pin"] is not None
    assert "json" not in result["content"]


def test_parse_json_with_backtick_artifacts():
    content = 'Done! ```json\n{"action": "request_click"}\n```'
    result = _parse_response(content)
    assert result["request_click"] is True
    assert "```" not in result["content"]
    assert "json" not in result["content"]


def test_parse_move_map_fit_all():
    content = 'Adjusting the map! {"action": "move_map", "target": "fit_all"}'
    result = _parse_response(content)
    assert result["move_map"] is not None
    assert result["move_map"]["target"] == "fit_all"
    assert result["content"] == "Adjusting the map!"


def test_parse_move_map_center():
    content = 'Centering on the bakery. {"action": "move_map", "target": "center", "lat": -23.56, "lng": -46.65, "zoom": 16}'
    result = _parse_response(content)
    assert result["move_map"]["target"] == "center"
    assert result["move_map"]["lat"] == -23.56
    assert result["move_map"]["lng"] == -46.65
    assert result["move_map"]["zoom"] == 16


def test_parse_move_map_location():
    content = 'Moving to São Paulo! {"action": "move_map", "target": "location", "address": "São Paulo, Brazil"}'
    result = _parse_response(content)
    assert result["move_map"]["target"] == "location"
    assert result["move_map"]["address"] == "São Paulo, Brazil"


def test_parse_clear_chat():
    content = 'Chat cleared! {"action": "clear_chat"}'
    result = _parse_response(content)
    assert result["clear_chat"] is True
    assert result["content"] == "Chat cleared!"


# --- New tests ---


def test_parse_place_pin():
    content = 'Placing a pin for you! {"action": "place_pin", "address": "Av Paulista 1000, São Paulo", "category": "restaurant", "name": "Burger Place", "confidence": 0.9}'
    result = _parse_response(content)
    assert result["place_pin"] is not None
    assert result["place_pin"]["address"] == "Av Paulista 1000, São Paulo"
    assert result["place_pin"]["category"] == "restaurant"
    assert result["place_pin"]["name"] == "Burger Place"
    assert result["place_pin"]["confidence"] == 0.9
    assert result["content"] == "Placing a pin for you!"


def test_parse_place_pin_defaults():
    content = 'Done! {"action": "place_pin", "address": "Main St"}'
    result = _parse_response(content)
    assert result["place_pin"]["category"] == "other"
    assert result["place_pin"]["name"] is None
    assert result["place_pin"]["confidence"] is None


def test_parse_delete_pins_all():
    content = 'Clearing all pins! {"action": "delete_pins", "which": "all"}'
    result = _parse_response(content)
    assert result["delete_pins"] is not None
    assert result["delete_pins"]["which"] == "all"
    assert result["content"] == "Clearing all pins!"


def test_parse_delete_pins_drafts():
    content = 'Removing drafts. {"action": "delete_pins", "which": "drafts"}'
    result = _parse_response(content)
    assert result["delete_pins"]["which"] == "drafts"


def test_parse_delete_pins_named():
    content = 'Removing those. {"action": "delete_pins", "which": "named", "names": ["Cafe A", "Bakery B"]}'
    result = _parse_response(content)
    assert result["delete_pins"]["which"] == "named"
    assert result["delete_pins"]["names"] == ["Cafe A", "Bakery B"]


def test_parse_list_pins():
    content = 'Here are your pins: {"action": "list_pins"}'
    result = _parse_response(content)
    assert result["list_pins"] is True
    assert result["content"] == "Here are your pins:"


def test_parse_json_without_action_key_ignored():
    content = 'Some text with json {"foo": "bar"}'
    result = _parse_response(content)
    assert result["request_click"] is False
    assert result["classification"] is None
    assert result["place_pin"] is None
    assert result["content"] == content


def test_parse_empty_content():
    result = _parse_response("")
    assert result["content"] == ""
    assert result["request_click"] is False


def test_parse_classify_defaults():
    content = 'Classified! {"action": "classify"}'
    result = _parse_response(content)
    assert result["classification"]["category"] == "other"
    assert result["classification"]["name"] is None
    assert result["classification"]["confidence"] is None


def test_parse_move_map_defaults():
    content = 'Moving! {"action": "move_map"}'
    result = _parse_response(content)
    assert result["move_map"]["target"] == "fit_all"
    assert result["move_map"]["lat"] is None
    assert result["move_map"]["lng"] is None
    assert result["move_map"]["zoom"] is None


# --- Provider selection tests ---


def test_get_chat_model_default_openai():
    """Default provider (openai) returns a ChatOpenAI instance."""
    with patch.multiple("app.core.config", LLM_PROVIDER="openai", LLM_MODEL="gpt-4o-mini",
                        LLM_TEMPERATURE=0.3, LLM_BASE_URL="", LLM_API_KEY="test-key"):
        model = get_chat_model()
        from langchain_openai import ChatOpenAI
        assert isinstance(model, ChatOpenAI)


def test_get_chat_model_openai_with_base_url():
    """OpenAI provider respects LLM_BASE_URL for proxies like LiteLLM."""
    with patch.multiple("app.core.config", LLM_PROVIDER="openai", LLM_MODEL="gpt-4o-mini",
                        LLM_TEMPERATURE=0.5, LLM_BASE_URL="http://localhost:4000", LLM_API_KEY="test-key"):
        model = get_chat_model()
        from langchain_openai import ChatOpenAI
        assert isinstance(model, ChatOpenAI)


def test_get_chat_model_unsupported_provider():
    """Unsupported provider raises ValueError with helpful message."""
    with patch.multiple("app.core.config", LLM_PROVIDER="unsupported", LLM_MODEL="some-model",
                        LLM_TEMPERATURE=0.3, LLM_BASE_URL="", LLM_API_KEY="test-key"):
        with pytest.raises(ValueError, match="Unsupported LLM_PROVIDER='unsupported'"):
            get_chat_model()


def test_get_chat_model_missing_package():
    """Missing provider package raises ImportError with install instructions."""
    with patch.multiple("app.core.config", LLM_PROVIDER="anthropic", LLM_MODEL="claude-3-haiku",
                        LLM_TEMPERATURE=0.3, LLM_BASE_URL="", LLM_API_KEY="test-key"), \
         patch.dict("sys.modules", {"langchain_anthropic": None}):
        with pytest.raises(ImportError, match="langchain-anthropic is required"):
            get_chat_model()


def test_get_chat_model_missing_api_key():
    """Missing LLM_API_KEY raises ValueError with helpful message."""
    with patch.multiple("app.core.config", LLM_PROVIDER="openai", LLM_MODEL="gpt-4o-mini",
                        LLM_TEMPERATURE=0.3, LLM_BASE_URL="", LLM_API_KEY=""):
        with pytest.raises(ValueError, match="LLM_API_KEY is required"):
            get_chat_model()
