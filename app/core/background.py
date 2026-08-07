"""
Wrapper around FastAPI's BackgroundTasks for fire-and-forget work
(report generation, embedding ingestion, ML retraining triggers)
so route handlers return immediately instead of blocking on slow work.

For anything that must survive a server restart or run on a schedule,
graduate this to Celery/RQ + Redis - this module is intentionally the
simplest thing that unblocks the "no loading for simple actions" goal.
"""
from fastapi import BackgroundTasks
import logging

logger = logging.getLogger("smart_automation_ai.background")


def run_async_job(background_tasks: BackgroundTasks, job_name: str, fn, *args, **kwargs):
    """Schedule fn(*args, **kwargs) to run after the response is sent."""
    def _wrapped():
        try:
            logger.info(f"Background job started: {job_name}")
            fn(*args, **kwargs)
            logger.info(f"Background job completed: {job_name}")
        except Exception as e:
            logger.error(f"Background job failed: {job_name} | {e}")

    background_tasks.add_task(_wrapped)
