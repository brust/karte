from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./karte.db")
GOOGLE_MAPS_API_KEY: str = os.getenv("GOOGLE_MAPS_API_KEY", "")

# LLM configuration
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai")
LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))
LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "")

# Provider API keys (read by LangChain automatically, listed here for documentation)
# OPENAI_API_KEY — required when LLM_PROVIDER=openai
# ANTHROPIC_API_KEY — required when LLM_PROVIDER=anthropic
# GOOGLE_API_KEY — required when LLM_PROVIDER=google
