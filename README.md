# Jellytics

> Jellyfin analytics and notification tool — the Tautulli for Jellyfin.

**The key differentiator:** A proper notification system with Jinja2 templating and configurable triggers, powered by [Apprise](https://github.com/caronc/apprise) (100+ services: Discord, Telegram, Slack, Pushover, Ntfy, Gotify, email, and more).

## Features

- 📡 **Webhook receiver** — captures `PlaybackStart`, `PlaybackProgress`, `PlaybackStop`, `ItemAdded` events from the Jellyfin webhook plugin
- 🗄️ **SQLite storage** — zero-dependency, single-file database (Postgres supported via env var)
- 📊 **Dashboard** — recent plays, currently streaming, top users, top content, 30-day stats
- 📜 **Watch history** — paginated, filterable by user and media type
- 🔔 **Notifications** — Apprise-powered, Jinja2-templated, condition-filtered alerts to any of 100+ services
- 🐳 **Docker Compose** — single container, persistent volume

## Quick Start

### 1. Configure Jellytics

```bash
cp config.example.yaml config.yaml
cp .env.example .env
# Edit config.yaml with your Jellyfin URL, API key, and notification agents
```

### 2. Run with Docker Compose

```bash
docker compose up -d
```

Jellytics starts on **http://localhost:8234**.

### 3. Configure Jellyfin Webhook Plugin

Install the [Jellyfin Webhook Plugin](https://github.com/jellyfin/jellyfin-plugin-webhook) and add a Generic Destination:

- **URL:** `http://your-jellytics-host:8234/webhook/jellyfin`
- **Notification Type:** `PlaybackStart`, `PlaybackProgress`, `PlaybackStop`, `ItemAdded`
- **Send All Properties:** ✅

## Configuration

```yaml
# config.yaml
jellyfin:
  url: "http://192.168.1.100:8096"
  api_key: "your_api_key"

notifications:
  agents:
    - name: "Discord"
      url: "discord://webhook_id/webhook_token"
      triggers: [playback_start, item_added]
      template: "default"

    - name: "Telegram"
      url: "tgram://bot_token/chat_id"
      triggers: [item_added]
      template: "item_added"

    - name: "Ntfy"
      url: "ntfy://ntfy.sh/my-jellyfin-topic"
      triggers: [playback_start, playback_stop]

  conditions:
    # Optional filters
    # media_types: [Movie, Episode]
    # users: [alice, bob]
```

See `config.example.yaml` for full documentation and [Apprise wiki](https://github.com/caronc/apprise/wiki) for notification URL formats.

## Notification Templates

Templates live in `jellytics/templates/notifications/` and use Jinja2 syntax.

Available variables (all Jellyfin webhook fields plus derived):
- `NotificationUsername`, `UserId`
- `Name`, `display_title`, `Type`, `Year`, `Genres`
- `SeriesName`, `SeasonNumber`, `EpisodeNumber`
- `ClientName`, `DeviceName`
- `PlayMethod`, `is_transcode`
- `completion_pct`, `PlayedToCompletion`
- `video_resolution`, `Bitrate`, `VideoCodec`, `AudioCodec`
- `NotificationType`

Custom templates: create `yourname.title.j2` and `yourname.body.j2` in the notifications directory, then set `template: yourname` in your agent config.

## Development

```bash
pip install -e ".[dev]"
cp config.example.yaml config.yaml
# Edit config.yaml

# Run dev server
uvicorn jellytics.main:app --reload --port 8234

# Run tests
pytest
```

## Architecture

```
jellytics/
├── main.py              # FastAPI app, lifespan setup
├── config.py            # YAML + env var config loading
├── database.py          # SQLAlchemy async engine
├── models.py            # ORM: User, Item, PlaySession, WatchHistory, NotificationLog
├── schemas.py           # Pydantic webhook payload schema
├── webhook.py           # /webhook/jellyfin endpoint, event handlers
├── dashboard.py         # Dashboard + history HTML routes
├── notifications.py     # Apprise dispatch + Jinja2 templating
└── templates/
    ├── base.html
    ├── dashboard.html
    ├── history.html
    └── notifications/
        ├── default.title.j2
        ├── default.body.j2
        ├── item_added.title.j2
        └── item_added.body.j2
```

## Roadmap

- [ ] Newsletter (weekly/monthly email digest)
- [ ] Transcode analytics page
- [ ] Library stats (storage, quality distribution)
- [ ] Advanced notification conditions (bitrate, resolution thresholds)
- [ ] Script notification agent
- [ ] IP geolocation (MaxMind GeoLite2)
- [ ] Prometheus metrics endpoint
- [ ] Multi-server support
- [ ] Import from Playback Reporting plugin

## License

MIT
