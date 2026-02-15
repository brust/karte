from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import config
from app.db.session import get_db
from app.models import ChatMessage, Pin
from app.routes.chat import router as chat_router
from app.routes.map import router as map_router
from app.routes.pins import router as pins_router

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Karte")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

app.include_router(chat_router)
app.include_router(map_router)
app.include_router(pins_router)


@app.get("/")
async def index(request: Request, db: AsyncSession = Depends(get_db)):
    pins_result = await db.execute(select(Pin))
    pins = [
        {
            "id": p.id,
            "lat": p.lat,
            "lng": p.lng,
            "name": p.name,
            "category": p.category,
            "status": p.status.value,
        }
        for p in pins_result.scalars().all()
    ]

    msgs_result = await db.execute(select(ChatMessage).order_by(ChatMessage.created_at))
    messages = msgs_result.scalars().all()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "google_maps_api_key": config.GOOGLE_MAPS_API_KEY,
            "pins": pins,
            "messages": messages,
        },
    )
