from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import ChatMessage, Pin, PinStatus
from app.services.geocode import geocode
from app.services.llm import get_assistant_response

router = APIRouter(prefix="/chat", tags=["chat"])
templates = Jinja2Templates(directory="app/templates")


@router.post("/send")
async def send_message(
    request: Request,
    message: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    # Save user message
    user_msg = ChatMessage(role="user", content=message)
    db.add(user_msg)
    await db.commit()

    # Build conversation history and current map state for LLM
    result = await db.execute(select(ChatMessage).order_by(ChatMessage.created_at))
    all_messages = result.scalars().all()
    history = [{"role": m.role, "content": m.content} for m in all_messages]

    pins_result = await db.execute(select(Pin))
    pins = [
        {"lat": p.lat, "lng": p.lng, "name": p.name, "category": p.category, "status": p.status.value}
        for p in pins_result.scalars().all()
    ]

    # Get assistant response
    llm_result = get_assistant_response(history, pins=pins)

    draft_pin = None
    place_pin = llm_result.get("place_pin")

    if place_pin and place_pin.get("address"):
        # Geocode the address and create a draft pin
        geo = geocode(place_pin["address"])
        if geo:
            # Check for duplicate at same location
            tol = 0.0001  # ~11 meters
            existing = await db.execute(
                select(Pin).where(
                    and_(
                        Pin.lat.between(geo["lat"] - tol, geo["lat"] + tol),
                        Pin.lng.between(geo["lng"] - tol, geo["lng"] + tol),
                    )
                )
            )
            if existing.scalars().first():
                llm_result["content"] += f"\n\nA pin already exists at that location ({geo['formatted_address']}). No duplicate created."
            else:
                pin = Pin(
                    lat=geo["lat"],
                    lng=geo["lng"],
                    name=place_pin.get("name"),
                    category=place_pin.get("category", "other"),
                    status=PinStatus.draft,
                    confidence=place_pin.get("confidence"),
                )
                db.add(pin)
                await db.commit()
                await db.refresh(pin)
                draft_pin = pin
                llm_result["content"] += f"\n\n📍 Found at: {geo['formatted_address']}"
        else:
            llm_result["content"] += "\n\nI couldn't find that address. Could you be more specific, or click on the map instead?"
            llm_result["request_click"] = True

    # Handle delete_pins action
    delete_action = llm_result.get("delete_pins")
    if delete_action:
        which = delete_action.get("which", "all")
        if which == "all":
            await db.execute(delete(Pin))
        elif which == "drafts":
            await db.execute(delete(Pin).where(Pin.status == PinStatus.draft))
        elif which == "named":
            names = delete_action.get("names", [])
            if names:
                await db.execute(delete(Pin).where(Pin.name.in_(names)))
        await db.commit()

    # Save assistant message
    assistant_msg = ChatMessage(role="assistant", content=llm_result["content"])
    db.add(assistant_msg)
    await db.commit()

    # Re-fetch all messages
    result = await db.execute(select(ChatMessage).order_by(ChatMessage.created_at))
    messages = result.scalars().all()

    return templates.TemplateResponse(
        "partials/chat_messages.html",
        {
            "request": request,
            "messages": messages,
            "request_click": llm_result.get("request_click", False),
            "draft_pin": draft_pin,
        },
    )
