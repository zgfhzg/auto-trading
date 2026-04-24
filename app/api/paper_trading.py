"""Paper trading API router."""

from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter

from app.services.paper_trading import (
    get_account_summary,
    get_return_report,
    initialize_account,
    list_positions,
)

router = APIRouter(prefix="/paper", tags=["paper-trading"])


class PaperPosition(BaseModel):
    symbol: str = ""
    quantity: int = 0
    avg_price: float = 0.0
    market_price: float = 0.0
    unrealized_pnl: float = 0.0


class PaperSummary(BaseModel):
    mode: str = "paper"
    starting_cash: float = 0.0
    cash: float = 0.0
    market_value: float = 0.0
    equity: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    total_fees: float = 0.0
    total_taxes: float = 0.0
    cumulative_return: float = 0.0
    positions: list[PaperPosition] = Field(default_factory=list)
    commission_rate: float = 0.0
    tax_rate: float = 0.0


class DailySnapshot(BaseModel):
    snapshot_date: str = ""
    equity: float = 0.0
    cash: float = 0.0
    market_value: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    daily_return: float = 0.0
    cumulative_return: float = 0.0


class SymbolReturn(BaseModel):
    symbol: str = ""
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    total_pnl: float = 0.0


class PaperReportResponse(BaseModel):
    summary: PaperSummary = Field(default_factory=PaperSummary)
    daily_snapshots: list[DailySnapshot] = Field(default_factory=list)
    today_return: float = 0.0
    cumulative_return: float = 0.0
    symbol_returns: list[SymbolReturn] = Field(default_factory=list)
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    mdd: float = 0.0


@router.get("/account")
def get_account() -> dict:
    return get_account_summary()


@router.get("/positions")
def get_positions() -> dict:
    return {"positions": list_positions()}


@router.get("/report", response_model=PaperReportResponse)
def get_report(limit: int = 30) -> PaperReportResponse:
    return PaperReportResponse.model_validate(get_return_report(limit))


@router.post("/reset")
def reset_account() -> dict:
    return initialize_account(reset=True)
