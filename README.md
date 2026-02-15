# Karte

A personal web app with a split-panel UI: **Google Maps** on the left, **AI chat** on the right. The assistant helps you place, classify, and manage pins on the map through natural conversation.

## Stack

- **FastAPI** + **Jinja2** + **HTMX** (server-rendered, no SPA)
- **SQLite** + **SQLAlchemy 2.x** (async) + **Alembic**
- **OpenAI Python SDK** via **LiteLLM** gateway
- **Google Maps JavaScript API** + Geocoding API

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

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | SQLAlchemy async database URL | `sqlite+aiosqlite:///./karte.db` |
| `GOOGLE_MAPS_API_KEY` | Google Maps JS + Geocoding API key | (required) |
| `LITELLM_BASE_URL` | LiteLLM gateway URL | `http://localhost:4000` |
| `OPENAI_API_KEY` | API key for the LLM gateway | (required) |
| `LLM_MODEL` | Model name sent to the gateway | `gpt-4o-mini` |

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

1. **Chat** with the assistant in the right panel.
2. **Mention a place** by name or address — the assistant geocodes it and places a draft pin automatically.
3. **Or click the map** — when no address is available, the assistant asks for a map click.
4. The assistant **classifies** the location into a category with a confidence score.
5. **Confirm or edit** the pin — it becomes a permanent marker.
6. **Ask questions** — "how many pins?", "list all pins", "delete all drafts", etc.

## Assistant capabilities

The AI assistant can perform these actions through chat:

| Action | Example prompt | What happens |
|--------|---------------|--------------|
| **Place pin** | "Add a bakery on Paulista Avenue" | Geocodes address, creates draft pin |
| **Map click** | "Add a pin" (no address) | Enables map click mode |
| **Classify** | _(automatic on map click)_ | Suggests category, name, confidence |
| **List pins** | "Show all pins" | Renders styled pin cards |
| **Delete pins** | "Clear all pins" / "Remove drafts" | Deletes matching pins |
| **Answer questions** | "How many restaurants?" | Responds using current map state |

Pin categories: `school`, `health_clinic`, `bakery`, `supermarket`, `pharmacy`, `restaurant`, `cafe`, `bank`, `park`, `other`.

## System prompt

The assistant receives the following system prompt on every request (defined in `app/services/llm.py`):

```
You are Karte, a helpful map assistant. You help users place and classify pins on a map.

Available categories: school, health_clinic, bakery, supermarket, pharmacy, restaurant, cafe, bank, park, other.

Actions — append EXACTLY ONE JSON block at the END of your message when needed:

1. Place a pin by address/name:
   {"action": "place_pin", "address": "...", "category": "...", "name": "...", "confidence": 0.0-1.0}

2. Request a map click (only when no address/name is given):
   {"action": "request_click"}

3. Classify coordinates (on map click):
   {"action": "classify", "category": "...", "name": "...", "confidence": 0.0-1.0, "reasoning": "..."}

4. Delete pins:
   {"action": "delete_pins", "which": "all|drafts|named", "names": ["..."]}

5. List pins:
   {"action": "list_pins"}

6. Move/pan the map:
   {"action": "move_map", "target": "fit_all"}
   {"action": "move_map", "target": "center", "lat": ..., "lng": ..., "zoom": 2-20}
   {"action": "move_map", "target": "location", "address": "..."}

Rules:
- Use actions for ADD, REMOVE, CLASSIFY, LIST, or MAP NAVIGATION only.
- Prefer place_pin over request_click whenever possible.
- Respond in the same language the user is using.
```

A second system message is injected with the current map state (all pins with name, category, status, and coordinates) so the assistant can answer questions and navigate to specific pins.

## API routes

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Main page with map + chat |
| `POST` | `/chat/send` | Send chat message, get assistant response |
| `GET` | `/map/pins` | All pins as JSON |
| `POST` | `/map/click` | Create draft pin from map coordinates |
| `POST` | `/pins/{id}/confirm` | Confirm/edit a draft pin |

## Project structure

```
app/
  main.py                  # FastAPI app, root route, router registration
  core/config.py           # Environment variable settings
  db/session.py            # Async SQLAlchemy session factory
  models/
    pin.py                 # Pin model (lat, lng, name, category, status, confidence)
    chat.py                # ChatMessage model (role, content)
  routes/
    chat.py                # POST /chat/send
    map.py                 # GET /map/pins, POST /map/click
    pins.py                # POST /pins/{id}/confirm
  services/
    llm.py                 # LLM orchestration, system prompt, action parsing
    geocode.py             # Google Maps Geocoding API wrapper
  templates/
    base.html              # Base layout (HTMX, head/content/scripts blocks)
    index.html             # Split-panel page (map + chat)
    partials/
      chat_messages.html   # Chat message loop + conditional widgets
      pin_confirm.html     # Draft pin confirmation form
      pin_list.html        # Styled pin cards
      pins.html            # Pin data injection for JS
  static/
    css/style.css          # Layout, chat, pin cards, typing indicator
    js/app.js              # Google Maps, markers, chat UX, HTMX hooks
alembic/                   # Database migrations
tests/
  test_routes.py           # Route integration tests (6 tests)
  test_llm.py              # LLM response parsing unit tests (4 tests)
  conftest.py              # In-memory DB + async client fixtures
```

## Database schema

**pins**
| Column | Type | Notes |
|--------|------|-------|
| id | Integer | PK |
| lat | Float | |
| lng | Float | |
| name | String | nullable |
| category | String | default `other` |
| status | Enum | `draft` / `confirmed` |
| confidence | Float | nullable, 0.0-1.0 |
| created_at | DateTime | auto |
| updated_at | DateTime | auto |

**chat_messages**
| Column | Type | Notes |
|--------|------|-------|
| id | Integer | PK |
| role | String | `user` / `assistant` / `system` |
| content | Text | |
| created_at | DateTime | auto |

Duplicate pins at the same location (within ~11m) are rejected.

## Tests

```bash
pytest
```

10 tests covering routes (index, pins CRUD, map click, chat send) and LLM response parsing.
