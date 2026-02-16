from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models import ChatMessage, Pin, PinStatus


def _llm_result(**overrides):
    """Build a complete mock LLM result dict with sensible defaults."""
    base = {
        "content": "OK",
        "request_click": False,
        "classification": None,
        "place_pin": None,
        "delete_pins": None,
        "list_pins": False,
        "move_map": None,
        "clear_chat": False,
    }
    base.update(overrides)
    return base


# --- Index ---


@pytest.mark.asyncio
async def test_index_returns_200(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "Karte" in resp.text


# --- Map pins ---


@pytest.mark.asyncio
async def test_get_pins_empty(client):
    resp = await client.get("/map/pins")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_pins_returns_existing(client, db_session):
    pin = Pin(lat=1.0, lng=2.0, category="bakery", status=PinStatus.confirmed)
    db_session.add(pin)
    await db_session.commit()

    resp = await client.get("/map/pins")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["category"] == "bakery"
    assert data[0]["status"] == "confirmed"


# --- Map click ---


@pytest.mark.asyncio
async def test_map_click_creates_draft_pin(client, db_session):
    mock = _llm_result(
        content="I see a location. Let me classify it.",
        classification={"category": "restaurant", "name": "Test Place", "confidence": 0.8, "reasoning": "test"},
    )
    with patch("app.routes.map.get_assistant_response", return_value=mock):
        resp = await client.post("/map/click", data={"lat": "1.5", "lng": "2.5"})

    assert resp.status_code == 200

    result = await db_session.execute(select(Pin))
    pins = result.scalars().all()
    assert len(pins) == 1
    assert pins[0].status == PinStatus.draft
    assert pins[0].category == "restaurant"
    assert pins[0].name == "Test Place"


@pytest.mark.asyncio
async def test_map_click_duplicate_location_no_new_pin(client, db_session):
    """Clicking the same spot twice should not create a duplicate pin."""
    existing = Pin(lat=1.5, lng=2.5, category="cafe", status=PinStatus.confirmed)
    db_session.add(existing)
    await db_session.commit()

    resp = await client.post("/map/click", data={"lat": "1.5", "lng": "2.5"})
    assert resp.status_code == 200

    result = await db_session.execute(select(Pin))
    pins = result.scalars().all()
    assert len(pins) == 1  # no duplicate


# --- Confirm pin ---


@pytest.mark.asyncio
async def test_confirm_pin(client, db_session):
    pin = Pin(lat=1.0, lng=2.0, category="other", status=PinStatus.draft)
    db_session.add(pin)
    await db_session.commit()
    await db_session.refresh(pin)

    resp = await client.post(
        f"/pins/{pin.id}/confirm",
        data={"name": "My Bakery", "category": "bakery"},
    )
    assert resp.status_code == 200

    await db_session.refresh(pin)
    assert pin.status == PinStatus.confirmed
    assert pin.name == "My Bakery"
    assert pin.category == "bakery"


@pytest.mark.asyncio
async def test_confirm_nonexistent_pin(client):
    resp = await client.post("/pins/9999/confirm", data={"name": "X", "category": "other"})
    assert resp.status_code == 200  # returns chat messages, no crash


# --- Chat send ---


@pytest.mark.asyncio
async def test_chat_send(client, db_session):
    mock = _llm_result(content="Hello! How can I help you?")
    with patch("app.routes.chat.get_assistant_response", return_value=mock):
        resp = await client.post("/chat/send", data={"message": "Hello"})

    assert resp.status_code == 200
    assert "Hello! How can I help you?" in resp.text

    result = await db_session.execute(select(ChatMessage).order_by(ChatMessage.created_at))
    messages = result.scalars().all()
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"


# --- Chat clear ---


@pytest.mark.asyncio
async def test_chat_clear_returns_empty(client, db_session):
    """clear_chat should wipe messages and return empty — no assistant reply persisted."""
    # Seed a message so there's something to clear
    db_session.add(ChatMessage(role="user", content="hi"))
    await db_session.commit()

    mock = _llm_result(content="Cleared!", clear_chat=True)
    with patch("app.routes.chat.get_assistant_response", return_value=mock):
        resp = await client.post("/chat/send", data={"message": "clear history"})

    assert resp.status_code == 200

    result = await db_session.execute(select(ChatMessage))
    messages = result.scalars().all()
    assert len(messages) == 0  # everything wiped, no assistant msg saved


# --- Delete pins via chat ---


@pytest.mark.asyncio
async def test_chat_delete_pins_all(client, db_session):
    db_session.add(Pin(lat=1.0, lng=2.0, category="cafe", status=PinStatus.confirmed))
    db_session.add(Pin(lat=3.0, lng=4.0, category="bank", status=PinStatus.draft))
    await db_session.commit()

    mock = _llm_result(content="All pins deleted.", delete_pins={"which": "all", "names": []})
    with patch("app.routes.chat.get_assistant_response", return_value=mock):
        resp = await client.post("/chat/send", data={"message": "delete all pins"})

    assert resp.status_code == 200

    result = await db_session.execute(select(Pin))
    assert len(result.scalars().all()) == 0


@pytest.mark.asyncio
async def test_chat_delete_pins_drafts_only(client, db_session):
    db_session.add(Pin(lat=1.0, lng=2.0, category="cafe", status=PinStatus.confirmed))
    db_session.add(Pin(lat=3.0, lng=4.0, category="bank", status=PinStatus.draft))
    await db_session.commit()

    mock = _llm_result(content="Drafts removed.", delete_pins={"which": "drafts", "names": []})
    with patch("app.routes.chat.get_assistant_response", return_value=mock):
        resp = await client.post("/chat/send", data={"message": "delete drafts"})

    assert resp.status_code == 200

    result = await db_session.execute(select(Pin))
    pins = result.scalars().all()
    assert len(pins) == 1
    assert pins[0].status == PinStatus.confirmed


@pytest.mark.asyncio
async def test_chat_delete_pins_named(client, db_session):
    db_session.add(Pin(lat=1.0, lng=2.0, name="Cafe A", category="cafe", status=PinStatus.confirmed))
    db_session.add(Pin(lat=3.0, lng=4.0, name="Bakery B", category="bakery", status=PinStatus.confirmed))
    await db_session.commit()

    mock = _llm_result(content="Removed Cafe A.", delete_pins={"which": "named", "names": ["Cafe A"]})
    with patch("app.routes.chat.get_assistant_response", return_value=mock):
        resp = await client.post("/chat/send", data={"message": "delete Cafe A"})

    assert resp.status_code == 200

    result = await db_session.execute(select(Pin))
    pins = result.scalars().all()
    assert len(pins) == 1
    assert pins[0].name == "Bakery B"


# --- Place pin via chat (with geocode) ---


@pytest.mark.asyncio
async def test_chat_place_pin_creates_draft(client, db_session):
    mock = _llm_result(
        content="Placing it!",
        place_pin={"address": "Av Paulista 1000", "category": "restaurant", "name": "Burger Place", "confidence": 0.9},
    )
    geo_result = {"lat": -23.56, "lng": -46.65, "formatted_address": "Av. Paulista, 1000, São Paulo"}

    with (
        patch("app.routes.chat.get_assistant_response", return_value=mock),
        patch("app.routes.chat.geocode", return_value=geo_result),
    ):
        resp = await client.post("/chat/send", data={"message": "add burger place on paulista"})

    assert resp.status_code == 200

    result = await db_session.execute(select(Pin))
    pins = result.scalars().all()
    assert len(pins) == 1
    assert pins[0].status == PinStatus.draft
    assert pins[0].name == "Burger Place"
    assert pins[0].category == "restaurant"


@pytest.mark.asyncio
async def test_chat_place_pin_geocode_fails_requests_click(client, db_session):
    mock = _llm_result(
        content="Let me find that.",
        place_pin={"address": "unknown place xyz", "category": "other", "name": None, "confidence": None},
    )

    with (
        patch("app.routes.chat.get_assistant_response", return_value=mock),
        patch("app.routes.chat.geocode", return_value=None),
    ):
        resp = await client.post("/chat/send", data={"message": "add pin at unknown place xyz"})

    assert resp.status_code == 200
    assert "couldn't find" in resp.text.lower() or "click on the map" in resp.text.lower()

    result = await db_session.execute(select(Pin))
    assert len(result.scalars().all()) == 0


@pytest.mark.asyncio
async def test_chat_place_pin_duplicate_skipped(client, db_session):
    """If a pin already exists at the geocoded location, no duplicate is created."""
    db_session.add(Pin(lat=-23.56, lng=-46.65, name="Existing", category="cafe", status=PinStatus.confirmed))
    await db_session.commit()

    mock = _llm_result(
        content="Placing it!",
        place_pin={"address": "Av Paulista 1000", "category": "restaurant", "name": "New Place", "confidence": 0.9},
    )
    geo_result = {"lat": -23.56, "lng": -46.65, "formatted_address": "Av. Paulista, 1000"}

    with (
        patch("app.routes.chat.get_assistant_response", return_value=mock),
        patch("app.routes.chat.geocode", return_value=geo_result),
    ):
        resp = await client.post("/chat/send", data={"message": "add place on paulista"})

    assert resp.status_code == 200
    assert "already exists" in resp.text.lower()

    result = await db_session.execute(select(Pin))
    assert len(result.scalars().all()) == 1  # no duplicate


# --- List pins via chat ---


@pytest.mark.asyncio
async def test_chat_list_pins(client, db_session):
    db_session.add(Pin(lat=1.0, lng=2.0, name="My Cafe", category="cafe", status=PinStatus.confirmed))
    await db_session.commit()

    mock = _llm_result(content="Here are your pins:", list_pins=True)
    with patch("app.routes.chat.get_assistant_response", return_value=mock):
        resp = await client.post("/chat/send", data={"message": "list pins"})

    assert resp.status_code == 200
    assert "My Cafe" in resp.text


@pytest.mark.asyncio
async def test_chat_list_pins_empty(client, db_session):
    mock = _llm_result(content="Here are your pins:", list_pins=True)
    with patch("app.routes.chat.get_assistant_response", return_value=mock):
        resp = await client.post("/chat/send", data={"message": "list pins"})

    assert resp.status_code == 200
    assert "No pins" in resp.text


# --- Move map via chat ---


@pytest.mark.asyncio
async def test_chat_move_map_location_geocodes(client, db_session):
    mock = _llm_result(
        content="Moving there!",
        move_map={"target": "location", "address": "Tokyo, Japan", "lat": None, "lng": None, "zoom": None},
    )
    geo_result = {"lat": 35.68, "lng": 139.69, "formatted_address": "Tokyo, Japan"}

    with (
        patch("app.routes.chat.get_assistant_response", return_value=mock),
        patch("app.routes.chat.geocode", return_value=geo_result),
    ):
        resp = await client.post("/chat/send", data={"message": "show me Tokyo"})

    assert resp.status_code == 200
    # The move_map data should be in the response for the JS to pick up
    assert "data-move-map" in resp.text


@pytest.mark.asyncio
async def test_chat_move_map_location_geocode_fails(client, db_session):
    mock = _llm_result(
        content="Moving there!",
        move_map={"target": "location", "address": "Nowhere XYZ", "lat": None, "lng": None, "zoom": None},
    )

    with (
        patch("app.routes.chat.get_assistant_response", return_value=mock),
        patch("app.routes.chat.geocode", return_value=None),
    ):
        resp = await client.post("/chat/send", data={"message": "go to Nowhere XYZ"})

    assert resp.status_code == 200
    # Should not crash, just no move_map in response
    assert "data-move-map" not in resp.text
