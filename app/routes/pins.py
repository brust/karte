from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.templates import templates
from app.db.session import get_db
from app.models import ChatMessage, Pin, PinStatus

router = APIRouter(prefix="/pins", tags=["pins"])


@router.post("/{pin_id}/confirm")
async def confirm_pin(
    request: Request,
    pin_id: int,
    name: str = Form(""),
    category: str = Form("other"),
    db: AsyncSession = Depends(get_db),
):
    pin = await db.get(Pin, pin_id)
    if pin is None:
        # Return messages with an error note
        result = await db.execute(select(ChatMessage).order_by(ChatMessage.created_at))
        messages = result.scalars().all()
        return templates.TemplateResponse(
            "partials/chat_messages.html",
            {"request": request, "messages": messages},
        )

    pin.name = name or None
    pin.category = category
    pin.status = PinStatus.confirmed
    await db.commit()

    # Add confirmation message
    display_name = name or category.replace("_", " ").title()
    confirm_msg = ChatMessage(
        role="assistant",
        content=f"Pin confirmed: {display_name} ({category.replace('_', ' ')}) at ({pin.lat:.5f}, {pin.lng:.5f}).",
    )
    db.add(confirm_msg)
    await db.commit()

    result = await db.execute(select(ChatMessage).order_by(ChatMessage.created_at))
    messages = result.scalars().all()

    return templates.TemplateResponse(
        "partials/chat_messages.html",
        {"request": request, "messages": messages},
    )
