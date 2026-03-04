"""Webhook receiver for Jellyfin events."""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jellytics.database import get_session
from jellytics.models import Item, PlaySession, User, WatchHistory
from jellytics.notifications import dispatch_notifications
from jellytics.schemas import JellyfinWebhookPayload

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook", tags=["webhook"])

TRIGGER_MAP = {
    "PlaybackStart": "playback_start",
    "PlaybackProgress": "playback_progress",
    "PlaybackStop": "playback_stop",
    "ItemAdded": "item_added",
}


async def _get_or_create_user(db: AsyncSession, payload: JellyfinWebhookPayload) -> User | None:
    if not payload.UserId:
        return None
    result = await db.execute(select(User).where(User.jellyfin_user_id == payload.UserId))
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            jellyfin_user_id=payload.UserId,
            username=payload.NotificationUsername or payload.UserId,
        )
        db.add(user)
        await db.flush()
    else:
        user.last_seen = datetime.utcnow()
        if payload.NotificationUsername:
            user.username = payload.NotificationUsername
    return user


async def _get_or_create_item(db: AsyncSession, payload: JellyfinWebhookPayload) -> Item | None:
    if not payload.ItemId:
        return None
    result = await db.execute(select(Item).where(Item.jellyfin_item_id == payload.ItemId))
    item = result.scalar_one_or_none()
    if not item:
        item = Item(
            jellyfin_item_id=payload.ItemId,
            title=payload.Name or "Unknown",
            media_type=payload.Type or "Unknown",
            year=payload.Year,
            series_name=payload.SeriesName or None,
            season_number=payload.SeasonNumber,
            episode_number=payload.EpisodeNumber,
            genres=", ".join(payload.Genres) if payload.Genres else None,
            runtime_ticks=payload.RunTimeTicks,
        )
        db.add(item)
        await db.flush()
    return item


@router.post("/jellyfin")
async def jellyfin_webhook(
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    """Receive events from the Jellyfin webhook plugin."""
    try:
        raw = await request.json()
    except Exception:
        # Some webhook plugin versions send form data
        form = await request.form()
        raw = dict(form)

    payload = JellyfinWebhookPayload(**raw)
    event_type = payload.NotificationType
    trigger = TRIGGER_MAP.get(event_type)

    logger.info("Webhook received: %s for %s by %s", event_type, payload.Name, payload.NotificationUsername)

    if event_type == "PlaybackStart":
        await _handle_playback_start(db, payload)
    elif event_type == "PlaybackProgress":
        await _handle_playback_progress(db, payload)
    elif event_type == "PlaybackStop":
        await _handle_playback_stop(db, payload)
    elif event_type == "ItemAdded":
        await _handle_item_added(db, payload)
    else:
        logger.debug("Unhandled event type: %s", event_type)

    if trigger:
        ctx = payload.to_template_context()
        await dispatch_notifications(trigger, ctx, db)

    return {"status": "ok", "event": event_type}


async def _handle_playback_start(db: AsyncSession, payload: JellyfinWebhookPayload) -> None:
    user = await _get_or_create_user(db, payload)
    item = await _get_or_create_item(db, payload)

    session = PlaySession(
        session_key=payload.DeviceId or None,
        user_id=user.id if user else None,
        item_id=item.id if item else None,
        device_name=payload.DeviceName or None,
        device_id=payload.DeviceId or None,
        client_name=payload.ClientName or None,
        remote_endpoint=payload.RemoteEndPoint or None,
        play_method=payload.PlayMethod or None,
        is_paused=payload.IsPaused,
        started_at=datetime.utcnow(),
        video_codec=payload.VideoCodec or None,
        audio_codec=payload.AudioCodec or None,
        video_resolution=payload.get_video_resolution(),
        bitrate=payload.Bitrate,
    )
    db.add(session)
    await db.commit()


async def _handle_playback_progress(db: AsyncSession, payload: JellyfinWebhookPayload) -> None:
    # Update the most recent open session for this device
    result = await db.execute(
        select(PlaySession)
        .where(PlaySession.device_id == payload.DeviceId)
        .where(PlaySession.stopped_at.is_(None))
        .order_by(PlaySession.started_at.desc())
    )
    session = result.scalar_one_or_none()
    if session:
        session.is_paused = payload.IsPaused
        session.position_ticks = payload.PlaybackPositionTicks
        session.completion_pct = payload.get_completion_pct()
        if payload.PlayMethod:
            session.play_method = payload.PlayMethod
        await db.commit()


async def _handle_playback_stop(db: AsyncSession, payload: JellyfinWebhookPayload) -> None:
    result = await db.execute(
        select(PlaySession)
        .where(PlaySession.device_id == payload.DeviceId)
        .where(PlaySession.stopped_at.is_(None))
        .order_by(PlaySession.started_at.desc())
    )
    session = result.scalar_one_or_none()

    user = await _get_or_create_user(db, payload)
    item = await _get_or_create_item(db, payload)

    now = datetime.utcnow()

    if session:
        session.stopped_at = now
        session.played_to_completion = payload.PlayedToCompletion
        session.completion_pct = payload.get_completion_pct()
        session.position_ticks = payload.PlaybackPositionTicks
        duration = (now - session.started_at).total_seconds()
        session.duration_seconds = duration
    else:
        # Create a stub session if we missed the start
        session = PlaySession(
            session_key=payload.DeviceId or None,
            user_id=user.id if user else None,
            item_id=item.id if item else None,
            device_name=payload.DeviceName or None,
            device_id=payload.DeviceId or None,
            client_name=payload.ClientName or None,
            remote_endpoint=payload.RemoteEndPoint or None,
            play_method=payload.PlayMethod or None,
            played_to_completion=payload.PlayedToCompletion,
            completion_pct=payload.get_completion_pct(),
            position_ticks=payload.PlaybackPositionTicks,
            started_at=now,
            stopped_at=now,
            video_codec=payload.VideoCodec or None,
            audio_codec=payload.AudioCodec or None,
            video_resolution=payload.get_video_resolution(),
            bitrate=payload.Bitrate,
        )
        db.add(session)
        await db.flush()

    # Write to denormalized watch history
    username = user.username if user else (payload.NotificationUsername or "Unknown")
    item_title = item.title if item else (payload.Name or "Unknown")
    display_title = item.display_title if item else item_title

    history = WatchHistory(
        session_id=session.id,
        username=username,
        item_title=item_title,
        display_title=display_title,
        media_type=payload.Type or "Unknown",
        client_name=payload.ClientName or None,
        device_name=payload.DeviceName or None,
        play_method=payload.PlayMethod or None,
        completion_pct=payload.get_completion_pct(),
        duration_seconds=session.duration_seconds,
        watched_at=now,
    )
    db.add(history)
    await db.commit()


async def _handle_item_added(db: AsyncSession, payload: JellyfinWebhookPayload) -> None:
    await _get_or_create_item(db, payload)
    await db.commit()
