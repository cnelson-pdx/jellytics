"""SQLAlchemy ORM models."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jellytics.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jellyfin_user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    last_seen: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    sessions: Mapped[list[PlaySession]] = relationship(back_populates="user")


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jellyfin_item_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(512))
    media_type: Mapped[str] = mapped_column(String(64))  # Movie, Episode, Audio, etc.
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    series_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    season_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    episode_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    genres: Mapped[str | None] = mapped_column(Text, nullable=True)  # comma-separated
    runtime_ticks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    sessions: Mapped[list[PlaySession]] = relationship(back_populates="item")

    @property
    def runtime_minutes(self) -> float | None:
        if self.runtime_ticks:
            return self.runtime_ticks / (10_000_000 * 60)
        return None

    @property
    def display_title(self) -> str:
        if self.series_name and self.season_number and self.episode_number:
            return f"{self.series_name} S{self.season_number:02d}E{self.episode_number:02d} — {self.title}"
        return self.title


class PlaySession(Base):
    __tablename__ = "play_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_key: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)

    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), nullable=True)

    # Device / client info
    device_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    device_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    client_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    remote_endpoint: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Playback
    play_method: Mapped[str | None] = mapped_column(String(32), nullable=True)  # Transcode/DirectStream/DirectPlay
    is_paused: Mapped[bool] = mapped_column(default=False)
    played_to_completion: Mapped[bool] = mapped_column(default=False)
    completion_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    position_ticks: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Timestamps
    started_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    # A/V stream info
    video_codec: Mapped[str | None] = mapped_column(String(32), nullable=True)
    audio_codec: Mapped[str | None] = mapped_column(String(32), nullable=True)
    video_resolution: Mapped[str | None] = mapped_column(String(32), nullable=True)
    bitrate: Mapped[int | None] = mapped_column(Integer, nullable=True)  # bps

    user: Mapped[User | None] = relationship(back_populates="sessions")
    item: Mapped[Item | None] = relationship(back_populates="sessions")

    @property
    def is_transcode(self) -> bool:
        return self.play_method == "Transcode"

    @property
    def duration_minutes(self) -> float | None:
        if self.duration_seconds:
            return self.duration_seconds / 60
        return None


class WatchHistory(Base):
    """Denormalized, pre-computed view for fast dashboard queries."""
    __tablename__ = "watch_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("play_sessions.id"))
    username: Mapped[str] = mapped_column(String(128), index=True)
    item_title: Mapped[str] = mapped_column(String(512))
    display_title: Mapped[str] = mapped_column(String(512))
    media_type: Mapped[str] = mapped_column(String(64), index=True)
    client_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    device_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    play_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    completion_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    watched_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class NotificationLog(Base):
    __tablename__ = "notification_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_name: Mapped[str] = mapped_column(String(128))
    trigger: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(256))
    body: Mapped[str] = mapped_column(Text)
    success: Mapped[bool] = mapped_column(default=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
