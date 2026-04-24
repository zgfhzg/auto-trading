"""News API router."""

from fastapi import APIRouter

from app.services.news import get_latest_news

router = APIRouter(prefix="/news", tags=["news"])


@router.get("/")
def list_news() -> dict:
    return {"items": get_latest_news()}
