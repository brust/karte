from __future__ import annotations

import logging

import httpx

from app.core import config

logger = logging.getLogger(__name__)


def geocode(address: str) -> dict | None:
    """Geocode an address using Google Maps Geocoding API.

    Returns {"lat": float, "lng": float, "formatted_address": str} or None.
    """
    try:
        resp = httpx.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={"address": address, "key": config.GOOGLE_MAPS_API_KEY},
            timeout=10,
        )
        data = resp.json()
        if data.get("status") != "OK" or not data.get("results"):
            logger.warning("Geocoding failed for %r: %s", address, data.get("status"))
            return None

        result = data["results"][0]
        loc = result["geometry"]["location"]
        return {
            "lat": loc["lat"],
            "lng": loc["lng"],
            "formatted_address": result.get("formatted_address", address),
        }
    except Exception:
        logger.exception("Geocoding error for %r", address)
        return None
