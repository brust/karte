from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models import ChatMessage, Pin, PinStatus


@pytest.mark.asyncio
async def test_index_returns_200(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "Karte" in resp.text


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


@pytest.mark.asyncio
async def test_map_click_creates_draft_pin(client, db_session):
    mock_result = {
        "content": "I see a location. Let me classify it.",
        "request_click": False,
        "classification": {"category": "restaurant", "name": "Test Place", "confidence": 0.8, "reasoning": "test"},
    }
    with patch("app.routes.map.get_assistant_response", return_value=mock_result):
        resp = await client.post("/map/click", data={"lat": "1.5", "lng": "2.5"})

    assert resp.status_code == 200

    result = await db_session.execute(select(Pin))
    pins = result.scalars().all()
    assert len(pins) == 1
    assert pins[0].status == PinStatus.draft
    assert pins[0].category == "restaurant"
    assert pins[0].name == "Test Place"


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
async def test_chat_send(client, db_session):
    mock_result = {
        "content": "Hello! How can I help you?",
        "request_click": False,
        "classification": None,
    }
    with patch("app.routes.chat.get_assistant_response", return_value=mock_result):
        resp = await client.post("/chat/send", data={"message": "Hello"})

    assert resp.status_code == 200
    assert "Hello! How can I help you?" in resp.text

    result = await db_session.execute(select(ChatMessage).order_by(ChatMessage.created_at))
    messages = result.scalars().all()
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"
