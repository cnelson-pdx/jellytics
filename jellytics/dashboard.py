"""Dashboard API routes and HTML rendering."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from jellytics.database import get_session
from jellytics.models import NotificationLog, PlaySession, User, WatchHistory

logger = logging.getLogger(__name__)
router = APIRouter(tags=["dashboard"])

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _utcnow() -> datetime:
    return datetime.utcnow()


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: AsyncSession = Depends(get_session)):
    now = _utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # Stats counts
    plays_today = (await db.execute(
        select(func.count()).select_from(WatchHistory).where(WatchHistory.watched_at >= today)
    )).scalar_one()

    plays_week = (await db.execute(
        select(func.count()).select_from(WatchHistory).where(WatchHistory.watched_at >= week_ago)
    )).scalar_one()

    plays_month = (await db.execute(
        select(func.count()).select_from(WatchHistory).where(WatchHistory.watched_at >= month_ago)
    )).scalar_one()

    # Recent plays (last 20)
    recent_result = await db.execute(
        select(WatchHistory).order_by(desc(WatchHistory.watched_at)).limit(20)
    )
    recent_plays = recent_result.scalars().all()

    # Currently playing (open sessions)
    active_result = await db.execute(
        select(PlaySession)
        .where(PlaySession.stopped_at.is_(None))
        .options(selectinload(PlaySession.user), selectinload(PlaySession.item))
        .order_by(desc(PlaySession.started_at))
    )
    active_sessions = active_result.scalars().all()

    # Top users (by play count, last 30 days)
    top_users_result = await db.execute(
        select(WatchHistory.username, func.count().label("plays"))
        .where(WatchHistory.watched_at >= month_ago)
        .group_by(WatchHistory.username)
        .order_by(desc("plays"))
        .limit(10)
    )
    top_users = top_users_result.all()

    # Top content (by play count, last 30 days)
    top_content_result = await db.execute(
        select(WatchHistory.display_title, WatchHistory.media_type, func.count().label("plays"))
        .where(WatchHistory.watched_at >= month_ago)
        .group_by(WatchHistory.display_title, WatchHistory.media_type)
        .order_by(desc("plays"))
        .limit(10)
    )
    top_content = top_content_result.all()

    # Recent notifications
    notif_result = await db.execute(
        select(NotificationLog).order_by(desc(NotificationLog.sent_at)).limit(10)
    )
    recent_notifications = notif_result.scalars().all()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "plays_today": plays_today,
        "plays_week": plays_week,
        "plays_month": plays_month,
        "recent_plays": recent_plays,
        "active_sessions": active_sessions,
        "top_users": top_users,
        "top_content": top_content,
        "recent_notifications": recent_notifications,
        "generated_at": now.strftime("%Y-%m-%d %H:%M UTC"),
    })


@router.get("/history", response_class=HTMLResponse)
async def watch_history(
    request: Request,
    db: AsyncSession = Depends(get_session),
    page: int = 1,
    user: str = "",
    media_type: str = "",
):
    per_page = 50
    offset = (page - 1) * per_page

    query = select(WatchHistory).order_by(desc(WatchHistory.watched_at))
    count_query = select(func.count()).select_from(WatchHistory)

    if user:
        query = query.where(WatchHistory.username == user)
        count_query = count_query.where(WatchHistory.username == user)
    if media_type:
        query = query.where(WatchHistory.media_type == media_type)
        count_query = count_query.where(WatchHistory.media_type == media_type)

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(query.offset(offset).limit(per_page))
    history = result.scalars().all()

    # Filter options
    users_result = await db.execute(select(WatchHistory.username).distinct().order_by(WatchHistory.username))
    all_users = [r[0] for r in users_result.all()]

    media_types_result = await db.execute(select(WatchHistory.media_type).distinct().order_by(WatchHistory.media_type))
    all_media_types = [r[0] for r in media_types_result.all()]

    return templates.TemplateResponse("history.html", {
        "request": request,
        "history": history,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
        "filter_user": user,
        "filter_media_type": media_type,
        "all_users": all_users,
        "all_media_types": all_media_types,
    })
