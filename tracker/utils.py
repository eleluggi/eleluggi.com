"""Utility helpers for the delivery tracker."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from functools import wraps
from typing import Callable, Iterable, Optional

import bleach
import markdown
from flask import abort, flash, g, redirect, url_for

from .models import Delivery, Role, Station

ALLOWED_MARKDOWN_TAGS = [
    "p",
    "strong",
    "em",
    "ul",
    "ol",
    "li",
    "br",
    "code",
    "pre",
    "blockquote",
    "a",
    "h1",
    "h2",
    "h3",
    "h4",
]
ALLOWED_MARKDOWN_ATTRS = {
    "a": ["href", "title", "rel"],
}


def markdown_safe(text: Optional[str]) -> str:
    """Render markdown-like text safely with limited tags."""
    if not text:
        return ""
    html = markdown.markdown(text, extensions=["extra", "sane_lists"])
    return bleach.clean(html, tags=ALLOWED_MARKDOWN_TAGS, attributes=ALLOWED_MARKDOWN_ATTRS, strip=True)


def role_required(*roles: Role) -> Callable:
    """Ensure the current user has at least one of the given roles."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = getattr(g, "current_user", None)
            if user is None:
                flash("Login erforderlich", "danger")
                return redirect(url_for("auth.login"))
            if roles and user.role not in roles:
                abort(403)
            return func(*args, **kwargs)

        return wrapper

    return decorator


def iso_week(value: date) -> int:
    return value.isocalendar().week


def determine_due_status(delivery: Delivery) -> Optional[str]:
    """Return textual due status for UI display."""
    if not delivery.ship_date:
        return None
    today = date.today()
    if delivery.ship_date < today:
        if delivery.current_station and delivery.current_station.name == "Versand abgeschlossen":
            return None
        return "overdue"
    if delivery.ship_date == today:
        return "today"
    if delivery.shipping_week == today.isocalendar().week:
        return "week"
    return "future"


def due_badge_class(status: Optional[str]) -> str:
    return {
        "overdue": "bg-danger",
        "today": "bg-warning text-dark",
        "week": "bg-info text-dark",
    }.get(status or "", "bg-secondary")


def priority_badge(priority: int) -> tuple[str, str]:
    mapping = {
        0: ("Normal", "bg-secondary"),
        1: ("Hoch", "bg-warning text-dark"),
        2: ("Kritisch", "bg-danger"),
    }
    return mapping.get(priority, (f"Priorität {priority}", "bg-secondary"))


def eta_for_station(station: Optional[Station]) -> Optional[datetime]:
    if station and station.default_duration_hours:
        return datetime.utcnow() + timedelta(hours=station.default_duration_hours)
    return None


def pagination_range(page: int, pages: int, span: int = 3) -> Iterable[int]:
    start = max(1, page - span)
    end = min(pages, page + span)
    return range(start, end + 1)
