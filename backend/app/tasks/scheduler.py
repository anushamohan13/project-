from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services.notifications import run_due_notification_jobs

settings = get_settings()
_scheduler = None


def _run_jobs() -> None:
    with SessionLocal() as db:
        run_due_notification_jobs(db)


def start_scheduler():
    global _scheduler
    if not settings.scheduler_enabled or settings.environment == "test" or _scheduler is not None:
        return _scheduler
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        return None
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        _run_jobs,
        "interval",
        seconds=max(settings.scheduler_interval_seconds, 10),
        id="notification-worker",
        replace_existing=True,
    )
    _scheduler.start()
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
