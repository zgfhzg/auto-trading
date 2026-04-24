"""FastAPI application entrypoint."""

from fastapi import FastAPI

from app.api.news import router as news_router
from app.api.paper_trading import router as paper_trading_router
from app.config import settings
from app.db import init_db


def create_app() -> FastAPI:
    settings.validate()

    app = FastAPI(title="Auto Trading API")

    @app.on_event("startup")
    def _startup() -> None:
        settings.validate()
        init_db()

    app.include_router(news_router)
    app.include_router(paper_trading_router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "paper_trading_enabled": settings.paper_trading_enabled}

    return app


app = create_app()
