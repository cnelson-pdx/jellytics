"""Tests for webhook receiver and data models."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from jellytics.main import app
from jellytics.database import init_db, engine, Base
from jellytics.config import _settings, load_settings
import jellytics.config as cfg_module


@pytest.fixture(autouse=True)
def set_test_settings():
    """Use in-memory SQLite for tests."""
    cfg_module._settings = None
    import os
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
    os.environ["JELLYFIN_URL"] = "http://localhost:8096"
    os.environ["JELLYFIN_API_KEY"] = "test"
    yield
    cfg_module._settings = None


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "jellytics"


@pytest.mark.asyncio
async def test_webhook_playback_start(client):
    payload = {
        "NotificationType": "PlaybackStart",
        "NotificationUsername": "alice",
        "UserId": "user-001",
        "Name": "Inception",
        "Type": "Movie",
        "ItemId": "item-001",
        "Year": 2010,
        "DeviceName": "Chrome",
        "DeviceId": "dev-001",
        "ClientName": "Jellyfin Web",
        "PlayMethod": "DirectPlay",
        "IsPaused": False,
        "RunTimeTicks": 8400000000,
    }
    response = await client.post("/webhook/jellyfin", json=payload)
    assert response.status_code == 200
    assert response.json()["event"] == "PlaybackStart"


@pytest.mark.asyncio
async def test_webhook_playback_stop(client):
    # First start
    start_payload = {
        "NotificationType": "PlaybackStart",
        "NotificationUsername": "bob",
        "UserId": "user-002",
        "Name": "The Matrix",
        "Type": "Movie",
        "ItemId": "item-002",
        "DeviceId": "dev-002",
        "ClientName": "Infuse",
        "PlayMethod": "DirectPlay",
    }
    await client.post("/webhook/jellyfin", json=start_payload)

    # Then stop
    stop_payload = {
        "NotificationType": "PlaybackStop",
        "NotificationUsername": "bob",
        "UserId": "user-002",
        "Name": "The Matrix",
        "Type": "Movie",
        "ItemId": "item-002",
        "DeviceId": "dev-002",
        "PlayMethod": "DirectPlay",
        "PlayedToCompletion": True,
        "PlaybackPositionTicks": 8200000000,
        "RunTimeTicks": 8400000000,
    }
    response = await client.post("/webhook/jellyfin", json=stop_payload)
    assert response.status_code == 200
    assert response.json()["event"] == "PlaybackStop"


@pytest.mark.asyncio
async def test_webhook_item_added(client):
    payload = {
        "NotificationType": "ItemAdded",
        "Name": "Dune: Part Two",
        "Type": "Movie",
        "ItemId": "item-003",
        "Year": 2024,
        "Genres": ["Sci-Fi", "Adventure"],
    }
    response = await client.post("/webhook/jellyfin", json=payload)
    assert response.status_code == 200
    assert response.json()["event"] == "ItemAdded"


@pytest.mark.asyncio
async def test_dashboard(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert b"Jellytics" in response.content


@pytest.mark.asyncio
async def test_history(client):
    response = await client.get("/history")
    assert response.status_code == 200


def test_webhook_payload_completion_pct():
    from jellytics.schemas import JellyfinWebhookPayload
    p = JellyfinWebhookPayload(
        NotificationType="PlaybackStop",
        PlaybackPositionTicks=4200000000,
        RunTimeTicks=8400000000,
    )
    assert p.get_completion_pct() == 50.0


def test_webhook_payload_display_title():
    from jellytics.schemas import JellyfinWebhookPayload
    p = JellyfinWebhookPayload(
        Name="Pilot",
        Type="Episode",
        SeriesName="Breaking Bad",
        SeasonNumber=1,
        EpisodeNumber=1,
    )
    ctx = p.to_template_context()
    assert ctx["display_title"] == "Breaking Bad S01E01 — Pilot"


def test_config_defaults():
    from jellytics.config import load_settings
    s = load_settings()
    assert s.server.port == 8234
    assert "sqlite" in s.database.url
