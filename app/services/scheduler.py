"""Scheduler registration utilities."""

from __future__ import annotations

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


class SchedulerLike:
    """Minimal scheduler protocol (e.g., APScheduler)."""

    def add_job(self, *args, **kwargs) -> None:  # pragma: no cover - interface only
        raise NotImplementedError


def register_news_collection_jobs(
    scheduler: SchedulerLike,
    collect_news_func: Callable[[], int],
    *,
    enable_10min_update: bool = False,
) -> None:
    """Register news collection tasks while keeping trading loop resilient."""

    safe_collect = _safe_job_wrapper(
        job_name="news collection",
        job_func=collect_news_func,
    )

    scheduler.add_job(
        safe_collect,
        trigger="cron",
        hour=8,
        minute=30,
        id="news_collect_daily_0830",
        replace_existing=True,
    )

    if enable_10min_update:
        scheduler.add_job(
            safe_collect,
            trigger="interval",
            minutes=10,
            id="news_collect_every_10m",
            replace_existing=True,
        )


def register_trading_loop_job(
    scheduler: SchedulerLike,
    trading_loop_func: Callable[[], None],
    *,
    interval_seconds: int,
) -> None:
    """Register auto-trading loop task using an interval trigger."""
    safe_trading_loop = _safe_job_wrapper(
        job_name="auto trading loop",
        job_func=trading_loop_func,
    )
    scheduler.add_job(
        safe_trading_loop,
        trigger="interval",
        seconds=interval_seconds,
        id="auto_trading_loop",
        replace_existing=True,
    )


def _safe_job_wrapper(job_name: str, job_func: Callable[[], object]) -> Callable[[], None]:
    def _safe_job() -> None:
        try:
            result = job_func()
            logger.info("%s finished. result=%s", job_name.capitalize(), result)
        except Exception:
            logger.exception("%s failed. Other scheduler jobs continue.", job_name.capitalize())

    return _safe_job
