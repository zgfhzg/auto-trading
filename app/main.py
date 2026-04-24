"""FastAPI application entrypoint."""

import logging

from fastapi import FastAPI

from app.api.news import router as news_router
from app.api.paper_trading import router as paper_trading_router
from app.config import settings
from app.db import init_db
from app.services.news_collector import RssNewsSource, collect_and_store
from app.services.paper_trading import initialize_account
from app.services.scheduler import register_news_collection_jobs, register_trading_loop_job

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings.validate()

    app = FastAPI(title="Auto Trading API")

    @app.on_event("startup")
    def _startup() -> None:
        from apscheduler.schedulers.background import BackgroundScheduler

        settings.validate()
        init_db()
        initialize_account()

        scheduler = BackgroundScheduler()
        app.state.scheduler = scheduler

        register_news_collection_jobs(
            scheduler=scheduler,
            collect_news_func=_collect_news_job,
            enable_10min_update=True,
        )
        register_trading_loop_job(
            scheduler=scheduler,
            trading_loop_func=_auto_trading_job,
            interval_seconds=settings.trade_interval_seconds,
        )
        scheduler.start()

    @app.on_event("shutdown")
    def _shutdown() -> None:
        scheduler = getattr(app.state, "scheduler", None)
        if scheduler is not None:
            scheduler.shutdown(wait=False)

    app.include_router(news_router)
    app.include_router(paper_trading_router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "paper_trading_enabled": settings.paper_trading_enabled}

    return app


app = create_app()


def _collect_news_job() -> int:
    source = RssNewsSource(feed_urls=settings.news_feed_urls)
    return collect_and_store(source)


def _auto_trading_job() -> None:
    logger.info("Auto trading cycle executed.")
