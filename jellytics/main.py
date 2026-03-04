"""Jellytics — main FastAPI application."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from jellytics.config import load_settings
from jellytics.dashboard import router as dashboard_router
from jellytics.database import init_db
from jellytics.webhook import router as webhook_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    logger.info("Starting Jellytics v0.1.0")
    logger.info("Database: %s", settings.database.url)
    logger.info("Jellyfin: %s", settings.jellyfin.url)

    # Ensure data directory exists
    if settings.database.url.startswith("sqlite"):
        db_path = settings.database.url.replace("sqlite+aiosqlite:///", "")
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

    await init_db()
    logger.info("Database initialized")
    yield
    logger.info("Shutting down Jellytics")


app = FastAPI(
    title="Jellytics",
    description="Jellyfin analytics and notification tool",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(dashboard_router)
app.include_router(webhook_router)

# Mount static files if the directory exists
import pathlib
static_dir = pathlib.Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/health")
async def health():
    return {"status": "ok", "app": "jellytics", "version": "0.1.0"}


def run():
    import uvicorn
    settings = load_settings()
    uvicorn.run(
        "jellytics.main:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
