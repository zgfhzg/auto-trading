"""Paper-trading service layer."""

from app.config import settings


def portfolio_snapshot() -> dict:
    return {
        "mode": "paper",
        "cash": settings.paper_trading_initial_cash,
        "positions": [],
        "commission_rate": settings.commission_rate,
        "tax_rate": settings.tax_rate,
    }
