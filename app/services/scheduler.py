from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.message_service import deliver_due_messages, run_random_push_cycle

scheduler = AsyncIOScheduler(timezone=settings.app_timezone)


def _scheduler_tick() -> None:
    with SessionLocal() as db:
        deliver_due_messages(db)
        run_random_push_cycle(db)


def start_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(
        _scheduler_tick,
        "interval",
        seconds=settings.npc_scheduler_interval_seconds,
        id="npc-message-tick",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)

