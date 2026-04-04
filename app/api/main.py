"""FastAPI app bootstrap and lifecycle wiring."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.config import get_settings
from app.logging import configure_logging
from app.scheduler import start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    scheduler = start_scheduler()
    app.state.scheduler = scheduler
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="weekly-options-scanner", lifespan=lifespan)
app.include_router(router, prefix="/api")

