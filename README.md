# Karte

A personal web app with a split UI: Google Maps on the left, AI chat on the right. The assistant guides you to click points on the map, creates pins, and classifies each pin into an establishment type.

## Stack

- **FastAPI** + **Jinja2** + **HTMX**
- **SQLite** + **SQLAlchemy 2.x** + **Alembic**
- **OpenAI Python SDK** via **LiteLLM** gateway

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Environment variables

Create a `.env` file:

```
DATABASE_URL=sqlite+aiosqlite:///./karte.db
GOOGLE_MAPS_API_KEY=your-key-here
LITELLM_BASE_URL=http://localhost:4000
OPENAI_API_KEY=your-key
LLM_MODEL=gpt-4o-mini
```

### Database

```bash
alembic upgrade head
```

### Run

```bash
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000

## How it works

1. Chat with the assistant in the right panel.
2. When asked to add a place, the assistant requests a map click.
3. Click the map — a draft pin (yellow marker) appears.
4. The assistant classifies the location (category, name, confidence).
5. Confirm or edit the pin — it becomes a permanent red marker.

## Tests

```bash
pytest
```
