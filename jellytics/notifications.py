"""Apprise-based notification system with Jinja2 templating."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import apprise
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.ext.asyncio import AsyncSession

from jellytics.config import NotificationAgent, get_settings
from jellytics.models import NotificationLog

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates" / "notifications"


def _get_jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )


def _render_template(template_name: str, context: dict[str, Any]) -> tuple[str, str]:
    """Render a notification template. Returns (title, body)."""
    env = _get_jinja_env()

    # Try agent-specific template first, then default
    for name in [template_name, "default"]:
        title_tpl = f"{name}.title.j2"
        body_tpl = f"{name}.body.j2"
        try:
            title = env.get_template(title_tpl).render(**context).strip()
            body = env.get_template(body_tpl).render(**context).strip()
            return title, body
        except Exception:
            continue

    # Fallback to inline
    event = context.get("NotificationType", "Event")
    title = context.get("display_title", context.get("Name", "Unknown"))
    body = f"{event}: {title} — {context.get('NotificationUsername', 'Unknown user')}"
    return event, body


def _check_conditions(context: dict[str, Any]) -> bool:
    """Return True if this event should trigger notifications."""
    settings = get_settings()
    cond = settings.notifications.conditions

    if cond.media_types and context.get("Type") not in cond.media_types:
        return False
    if cond.users and context.get("NotificationUsername") not in cond.users:
        return False
    return True


async def dispatch_notifications(
    trigger: str,
    context: dict[str, Any],
    db: AsyncSession,
) -> None:
    """Send notifications to all matching agents for this trigger."""
    settings = get_settings()
    agents = settings.notifications.agents

    if not agents:
        return

    if not _check_conditions(context):
        logger.debug("Notification conditions not met for trigger %s", trigger)
        return

    for agent in agents:
        if not agent.enabled:
            continue
        if trigger not in agent.triggers:
            continue
        await _send_to_agent(agent, trigger, context, db)


async def _send_to_agent(
    agent: NotificationAgent,
    trigger: str,
    context: dict[str, Any],
    db: AsyncSession,
) -> None:
    title, body = _render_template(agent.template, context)
    success = True
    error_msg = None

    try:
        ap = apprise.Apprise()
        ap.add(agent.url)
        result = await ap.async_notify(title=title, body=body)
        if not result:
            success = False
            error_msg = "Apprise returned False"
        logger.info("Notification sent to %s: %s", agent.name, title)
    except Exception as e:
        success = False
        error_msg = str(e)
        logger.error("Failed to send notification to %s: %s", agent.name, e)

    log_entry = NotificationLog(
        agent_name=agent.name,
        trigger=trigger,
        title=title,
        body=body,
        success=success,
        error_message=error_msg,
        sent_at=datetime.utcnow(),
    )
    db.add(log_entry)
    await db.commit()
