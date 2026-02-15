from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import ChatMessage, Pin, PinStatus
from app.services.llm import get_assistant_response

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
    # Create draft pin
    pin = Pin(lat=lat, lng=lng, status=PinStatus.draft, category="other")
    db.add(pin)
    await db.commit()
    await db.refresh(pin)

    # Add system message with coordinates to conversation
    coord_msg = ChatMessage(
        role="system",
        content=f"User clicked on the map at coordinates: lat={lat:.6f}, lng={lng:.6f}. Please classify this location.",
    )
    db.add(coord_msg)
    await db.commit()

    # Build conversation history and current map state for LLM
    result = await db.execute(select(ChatMessage).order_by(ChatMessage.created_at))
    all_messages = result.scalars().all()
    history = [{"role": m.role, "content": m.content} for m in all_messages]

    pins_result = await db.execute(select(Pin))
    pins_list = [
        {"lat": p.lat, "lng": p.lng, "name": p.name, "category": p.category, "status": p.status.value}
        for p in pins_result.scalars().all()
    ]

    llm_result = get_assistant_response(history, pins=pins_list)

    # Update pin with classification if available
    classification = llm_result.get("classification")
    if classification:
        pin.category = classification.get("category", "other")
        pin.name = classification.get("name")
        pin.confidence = classification.get("confidence")
        await db.commit()
        await db.refresh(pin)

    # Save assistant response
    assistant_msg = ChatMessage(role="assistant", content=llm_result["content"])
    db.add(assistant_msg)
    await db.commit()

    # Re-fetch all messages
    result = await db.execute(select(ChatMessage).order_by(ChatMessage.created_at))
    messages = result.scalars().all()

    return templates.TemplateResponse(
        "partials/chat_messages.html",
        {"request": request, "messages": messages, "draft_pin": pin},
    )
