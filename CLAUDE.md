# Karte

Karte is a server-rendered web app:
- Left: Google Maps panel for selecting locations and viewing pins
- Right: AI chat panel that guides pin placement and classifies places

## Stack
- FastAPI + Jinja2 + HTMX
- SQLite (initial), SQLAlchemy 2.x, Alembic
- LiteLLM gateway + OpenAI Python SDK (Responses-style calls where applicable)

## No Auth (for now)
This is single-user mode:
- No login/register/logout
- All pins and chat messages belong to the app instance

## Setup

### Env vars
- `DATABASE_URL` (default `sqlite:///./karte.db`)
- `GOOGLE_MAPS_API_KEY`
- `LITELLM_BASE_URL`
- `OPENAI_API_KEY` (if required by gateway)
- `LLM_MODEL`

### Run
- `python -m venv .venv`
- `source .venv/bin/activate`
- `pip install -r requirements.txt`
- `alembic upgrade head`
- `uvicorn app.main:app --reload`

Open `http://127.0.0.1:8000`

## UX Flow
1. User chats with the assistant.
2. Assistant can request a map click.
3. User clicks map -> a draft pin is created.
4. Assistant classifies into a constrained category list with confidence.
5. User confirms/edits -> pin becomes confirmed and persists.

## Pin Categories
Keep categories constrained, e.g.:
- school
- health_clinic
- bakery
- supermarket
- pharmacy
- restaurant
- cafe
- bank
- park
- other

## Architecture Notes
- Pages via Jinja2, fragments via HTMX in `templates/partials/`.
- DB changes always via Alembic migrations.
- LLM calls centralized in `app/services/llm.py`, model name from `LLM_MODEL`.

## Git Guidelines
Small commits, one feature per commit, push after each batch.