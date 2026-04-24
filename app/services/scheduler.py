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

    def _safe_collect() -> None:
        try:
            inserted = collect_news_func()
            logger.info("News collection finished. inserted=%s", inserted)
        except Exception:
            logger.exception(
                "News collection failed. Trading loop should continue without interruption."
            )

    scheduler.add_job(
        _safe_collect,
        trigger="cron",
        hour=8,
        minute=30,
        id="news_collect_daily_0830",
        replace_existing=True,
    )

    if enable_10min_update:
        scheduler.add_job(
            _safe_collect,
            trigger="interval",
            minutes=10,
            id="news_collect_every_10m",
            replace_existing=True,
        )
