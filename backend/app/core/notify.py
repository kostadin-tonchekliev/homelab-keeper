from __future__ import annotations

import httpx

from ..models import Settings
from .logbus import log_bus


def notify(settings: Settings, title: str, message: str, success: bool) -> None:
    """Best-effort webhook notification (ntfy/Discord/Gotify/generic JSON)."""
    url = (settings.notify_webhook_url or "").strip()
    if not url:
        return
    if success and not settings.notify_on_success:
        return
    if not success and not settings.notify_on_failure:
        return

    try:
        if "discord.com/api/webhooks" in url:
            payload = {"content": f"**{title}**\n{message}"}
            httpx.post(url, json=payload, timeout=15)
        elif "/message" in url:  # Gotify
            httpx.post(
                url,
                json={"title": title, "message": message, "priority": 5},
                timeout=15,
            )
        else:  # ntfy or generic: send the body as text with a title header
            httpx.post(url, data=message.encode(), headers={"Title": title}, timeout=15)
    except httpx.HTTPError as exc:
        log_bus.warning(f"Notification failed: {exc}")
