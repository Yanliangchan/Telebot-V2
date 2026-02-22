"""Shared conversation/session state helpers."""

from __future__ import annotations


def reset_session(context, mode: str | None = None) -> None:
    """Clear per-user state and optionally set a new mode."""
    context.user_data.clear()
    if mode:
        context.user_data["mode"] = mode
