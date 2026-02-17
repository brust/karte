# Karte

Karte is a server-rendered web app:
- Left: Google Maps panel for selecting locations and viewing pins
- Right: AI chat panel that guides pin placement and classifies places

## Stack
- FastAPI + Jinja2 + HTMX
- SQLite (initial), SQLAlchemy 2.x, Alembic
- LangChain for LLM access (supports OpenAI, Anthropic, Google, and custom endpoints)

## No Auth (for now)
This is single-user mode:
- No login/register/logout
- All pins and chat messages belong to the app instance

## Setup

### Env vars
- `DATABASE_URL` (default `sqlite+aiosqlite:///./karte.db`)
- `GOOGLE_MAPS_API_KEY`
- `LLM_PROVIDER` (default `openai`; also supports `anthropic`, `google`)
- `LLM_MODEL` (default `gpt-4o-mini`)
- `LLM_TEMPERATURE` (default `0.3`)
- `LLM_BASE_URL` (optional; for custom endpoints like LiteLLM)
- `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY` (provider-specific)

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
- LLM calls centralized in `app/services/llm.py` via LangChain; provider/model from env vars.

## Git Workflow
You are allowed to work directly on the `main` branch.
You may:
- Commit incrementally as you progress
- Push directly to `main`
- Skip creating a separate branch
- Skip opening a Pull Request
Use clear, descriptive commit messages.