"""AI Email Engine — FastAPI Application."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.api import sync, emails
from app.services.imap_sync import imap_sync

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("ai-email-engine")

# Background sync task handle
_sync_task: asyncio.Task = None


async def periodic_sync():
    """Background task that syncs emails on a schedule."""
    while True:
        try:
            await asyncio.sleep(settings.sync_interval_minutes * 60)

            if not imap_sync.is_connected:
                logger.info("Periodic sync: reconnecting to IMAP...")
                connected = await imap_sync.connect()
                if not connected:
                    logger.warning(f"Periodic sync: connection failed — {imap_sync.last_error}")
                    continue

            for folder in settings.sync_folder_list:
                logger.info(f"Periodic sync: syncing {folder}...")
                result = await imap_sync.sync_folder(folder=folder)
                if result.get("new_emails", 0) > 0:
                    logger.info(f"Periodic sync: {result['new_emails']} new in {folder}")

        except asyncio.CancelledError:
            logger.info("Periodic sync task cancelled")
            break
        except Exception as e:
            logger.error(f"Periodic sync error: {e}")
            await asyncio.sleep(30)  # Brief pause on error before retry


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    global _sync_task

    # Startup
    logger.info("=" * 60)
    logger.info("AI Email Engine starting up")
    logger.info(f"IMAP: {settings.imap_host}:{settings.imap_port}")
    logger.info(f"Database: {settings.database_url.split('@')[-1]}")
    logger.info(f"Sync interval: {settings.sync_interval_minutes} min")
    logger.info(f"Sync folders: {settings.sync_folder_list}")
    logger.info("=" * 60)

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Auto-connect to IMAP (non-blocking — failure is OK at startup)
    if settings.imap_user:
        connected = await imap_sync.connect()
        if connected:
            logger.info("IMAP connected at startup")

            # Run initial sync
            for folder in settings.sync_folder_list:
                logger.info(f"Initial sync: {folder}")
                result = await imap_sync.sync_folder(
                    folder=folder,
                    limit=settings.initial_sync_limit,
                )
                logger.info(f"Initial sync result: {result}")
        else:
            logger.warning(f"IMAP not connected at startup: {imap_sync.last_error}")
            logger.warning("Use POST /api/sync/connect to connect manually")

    # Start periodic sync
    _sync_task = asyncio.create_task(periodic_sync())
    logger.info("Periodic sync task started")

    yield

    # Shutdown
    logger.info("Shutting down...")
    if _sync_task:
        _sync_task.cancel()
        try:
            await _sync_task
        except asyncio.CancelledError:
            pass
    await imap_sync.disconnect()
    logger.info("Shutdown complete")


# Create app
app = FastAPI(
    title="AI Email Engine",
    description="AI-powered email processor for Proton Mail Bridge",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3100", "http://127.0.0.1:3100"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(sync.router)
app.include_router(emails.router)


@app.get("/")
async def root():
    """Root endpoint — basic info."""
    return {
        "app": "AI Email Engine",
        "version": "0.1.0",
        "status": "running",
        "imap_connected": imap_sync.is_connected,
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "imap_connected": imap_sync.is_connected,
        "imap_syncing": imap_sync.is_syncing,
    }
