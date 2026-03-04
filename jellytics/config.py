"""Configuration loading from YAML + environment variables."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings


class JellyfinConfig(BaseModel):
    url: str = "http://localhost:8096"
    api_key: str = ""


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8234
    public_url: str = "http://localhost:8234"


class DatabaseConfig(BaseModel):
    url: str = "sqlite+aiosqlite:///./data/jellytics.db"


class NotificationAgent(BaseModel):
    name: str
    url: str
    triggers: list[str] = ["playback_start", "playback_stop", "item_added"]
    template: str = "default"
    enabled: bool = True


class NotificationConditions(BaseModel):
    media_types: list[str] = []
    users: list[str] = []
    min_completion_pct: float = 0


class NotificationsConfig(BaseModel):
    agents: list[NotificationAgent] = []
    conditions: NotificationConditions = NotificationConditions()


class Settings(BaseModel):
    jellyfin: JellyfinConfig = JellyfinConfig()
    server: ServerConfig = ServerConfig()
    database: DatabaseConfig = DatabaseConfig()
    notifications: NotificationsConfig = NotificationsConfig()


_settings: Settings | None = None


def load_settings(config_path: str | None = None) -> Settings:
    global _settings
    if _settings is not None:
        return _settings

    path = config_path or os.environ.get("JELLYTICS_CONFIG", "./config.yaml")
    data: dict[str, Any] = {}

    if Path(path).exists():
        with open(path) as f:
            data = yaml.safe_load(f) or {}

    # Environment variable overrides
    if url := os.environ.get("JELLYFIN_URL"):
        data.setdefault("jellyfin", {})["url"] = url
    if key := os.environ.get("JELLYFIN_API_KEY"):
        data.setdefault("jellyfin", {})["api_key"] = key
    if db_url := os.environ.get("DATABASE_URL"):
        data.setdefault("database", {})["url"] = db_url
    if host := os.environ.get("JELLYTICS_HOST"):
        data.setdefault("server", {})["host"] = host
    if port := os.environ.get("JELLYTICS_PORT"):
        data.setdefault("server", {})["port"] = int(port)

    _settings = Settings(**data)
    return _settings


def get_settings() -> Settings:
    return load_settings()
