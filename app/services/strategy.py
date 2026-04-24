"""Trading strategy service layer."""

from __future__ import annotations

from app.services.news_signal import get_news_score


def generate_signal(
    symbol: str,
    *,
    ai_score: float = 0.0,
    price_score: float = 0.0,
    has_position: bool = False,
) -> dict:
    news_score = get_news_score(symbol)
    final_score = (news_score * 0.4) + (ai_score * 0.4) + (price_score * 0.2)

    new_buy_blocked = news_score <= -0.8
    buy_priority_weight = 1.5 if news_score >= 0.8 else 1.0
    forced_sell_review = has_position and news_score < -0.7

    if forced_sell_review:
        signal = "REVIEW_SELL"
        reason = "news_drawdown_risk"
    elif final_score >= 0.6 and not new_buy_blocked:
        signal = "BUY"
        reason = "score_threshold_met"
    elif final_score <= -0.6:
        signal = "SELL"
        reason = "score_threshold_breached"
    else:
        signal = "HOLD"
        reason = "no_action"

    if new_buy_blocked and signal == "BUY":
        signal = "HOLD"
        reason = "buy_blocked_by_negative_news"

    return {
        "symbol": symbol.upper(),
        "signal": signal,
        "reason": reason,
        "score": {
            "news": news_score,
            "ai": ai_score,
            "price": price_score,
            "final": final_score,
            "buy_priority_weight": buy_priority_weight,
        },
        "guards": {
            "new_buy_blocked": new_buy_blocked,
            "forced_sell_review": forced_sell_review,
        },
    }
