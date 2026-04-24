"""Paper trading API router."""

from __future__ import annotations

from fastapi import APIRouter

from app.services.paper_trading import (
    get_account_summary,
    get_return_report,
    initialize_account,
    list_positions,
)

router = APIRouter(prefix="/paper", tags=["paper-trading"])


@router.get("/account")
def get_account() -> dict:
    return get_account_summary()


@router.get("/positions")
def get_positions() -> dict:
    return {"positions": list_positions()}


@router.get("/report")
def get_report(limit: int = 30) -> dict:
    return get_return_report(limit)


@router.post("/reset")
def reset_account() -> dict:
    return initialize_account(reset=True)
