"""SQLAlchemy async database setup."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from jellytics.config import get_settings

engine = None
AsyncSessionLocal = None


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    global engine, AsyncSessionLocal
    settings = get_settings()
    engine = create_async_engine(settings.database.url, echo=False)
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _ensure_init() -> None:
    """Lazy init for test contexts where lifespan doesn't run."""
    global AsyncSessionLocal
    if AsyncSessionLocal is None:
        await init_db()


async def get_session():
    await _ensure_init()
    async with AsyncSessionLocal() as session:
        yield session
