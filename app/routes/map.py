from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import ChatMessage, Pin, PinStatus

router = APIRouter(prefix="/map", tags=["map"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/pins")
async def get_pins(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Pin))
    pins = result.scalars().all()
    return [
        {
            "id": p.id,
            "lat": p.lat,
            "lng": p.lng,
            "name": p.name,
            "category": p.category,
            "status": p.status.value,
            "confidence": p.confidence,
        }
        for p in pins
    ]


@router.post("/click")
async def map_click(
    request: Request,
    lat: float = Form(...),
    lng: float = Form(...),
    db: AsyncSession = Depends(get_db),
):
    pin = Pin(lat=lat, lng=lng, status=PinStatus.draft, category="other")
    db.add(pin)
    await db.commit()
    await db.refresh(pin)

    # Store assistant message about the draft pin
    assistant_msg = ChatMessage(
        role="assistant",
        content=f"Draft pin created at ({lat:.5f}, {lng:.5f}). Classifying…",
    )
    db.add(assistant_msg)
    await db.commit()

    # Return chat messages (will be swapped into #chat-messages)
    result = await db.execute(select(ChatMessage).order_by(ChatMessage.created_at))
    messages = result.scalars().all()

    return templates.TemplateResponse(
        "partials/chat_messages.html",
        {"request": request, "messages": messages, "draft_pin": pin},
    )
