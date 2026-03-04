"""Pydantic schemas for Jellyfin webhook payloads."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class JellyfinWebhookPayload(BaseModel):
    """Jellyfin webhook plugin payload schema."""
    model_config = {"extra": "allow"}

    # Event type
    NotificationType: str = ""

    # Server
    ServerId: str = ""
    ServerName: str = ""
    ServerVersion: str = ""
    ServerUrl: str = ""

    # User
    NotificationUsername: str = ""
    UserId: str = ""

    # Device / client
    DeviceName: str = ""
    DeviceId: str = ""
    ClientName: str = ""
    RemoteEndPoint: str = ""

    # Item
    Name: str = ""
    Type: str = ""  # Movie, Episode, Audio, etc.
    Year: int | None = None
    Genres: list[str] = Field(default_factory=list)
    RunTime: str = ""  # e.g. "2:04:30"
    RunTimeTicks: int | None = None
    ItemId: str = ""
    SeriesName: str = ""
    SeasonNumber: int | None = None
    EpisodeNumber: int | None = None

    # Playback
    PlaybackPositionTicks: int | None = None
    PlayMethod: str = ""  # Transcode / DirectStream / DirectPlay
    IsPaused: bool = False
    PlayedToCompletion: bool = False
    PlayCount: int | None = None
    Favorite: bool = False

    # A/V streams
    VideoCodec: str = ""
    AudioCodec: str = ""
    VideoHeight: int | None = None
    VideoWidth: int | None = None
    Bitrate: int | None = None

    def get_completion_pct(self) -> float | None:
        if self.PlaybackPositionTicks and self.RunTimeTicks and self.RunTimeTicks > 0:
            return round((self.PlaybackPositionTicks / self.RunTimeTicks) * 100, 1)
        return None

    def get_video_resolution(self) -> str | None:
        if self.VideoWidth and self.VideoHeight:
            return f"{self.VideoWidth}x{self.VideoHeight}"
        return None

    def to_template_context(self) -> dict[str, Any]:
        ctx = self.model_dump()
        ctx["completion_pct"] = self.get_completion_pct()
        ctx["video_resolution"] = self.get_video_resolution()
        ctx["is_transcode"] = self.PlayMethod == "Transcode"
        ctx["is_episode"] = self.Type == "Episode"
        ctx["display_title"] = (
            f"{self.SeriesName} S{self.SeasonNumber:02d}E{self.EpisodeNumber:02d} — {self.Name}"
            if self.SeriesName and self.SeasonNumber and self.EpisodeNumber
            else self.Name
        )
        return ctx
