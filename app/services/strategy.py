"""Trading strategy service layer."""


def generate_signal(symbol: str) -> dict:
    return {"symbol": symbol, "signal": "HOLD", "reason": "stub strategy"}
