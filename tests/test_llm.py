from __future__ import annotations

from app.services.llm import _parse_response


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
