from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import ChatMessage
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

    # Build conversation history for LLM
    result = await db.execute(select(ChatMessage).order_by(ChatMessage.created_at))
    all_messages = result.scalars().all()
    history = [{"role": m.role, "content": m.content} for m in all_messages]

    # Get assistant response
    llm_result = get_assistant_response(history)

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
        },
    )
