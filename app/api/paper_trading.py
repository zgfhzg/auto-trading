"""Paper trading API router."""

from fastapi import APIRouter

from app.services.paper_trading import portfolio_snapshot
from app.services.strategy import generate_signal

router = APIRouter(prefix="/paper", tags=["paper-trading"])


@router.get("/portfolio")
def get_portfolio() -> dict:
    return portfolio_snapshot()


@router.get("/signal/{symbol}")
def get_signal(symbol: str) -> dict:
    return generate_signal(symbol.upper())
