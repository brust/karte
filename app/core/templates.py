from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape

_dir = Path(__file__).resolve().parent.parent / "templates"

templates = Jinja2Templates(directory=_dir)
templates.env.filters["nl2br"] = lambda v: Markup(escape(v).replace("\n", Markup("<br>\n")))
