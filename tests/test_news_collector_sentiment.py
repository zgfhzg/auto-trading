import sys
import types

requests_stub = types.SimpleNamespace(
    RequestException=Exception,
    get=lambda *args, **kwargs: None,
)
sys.modules.setdefault("requests", requests_stub)
sys.modules.setdefault(
    "app.config",
    types.SimpleNamespace(settings=types.SimpleNamespace(symbol_keywords={})),
)
sys.modules.setdefault("app.db", types.SimpleNamespace(get_session=lambda: None))

from app.services.news_collector import _rule_based_sentiment


def test_rule_based_sentiment_positive_keywords() -> None:
    text = "삼성전자 호재로 급등, 수급 강세"
    assert _rule_based_sentiment(text) > 0.0


def test_rule_based_sentiment_negative_keywords() -> None:
    text = "실적 악재와 적자 지속으로 주가 급락"
    assert _rule_based_sentiment(text) < 0.0


def test_rule_based_sentiment_mixed_keywords() -> None:
    text = "호재가 있지만 단기 하락 우려도 공존"
    assert _rule_based_sentiment(text) == 0.0


def test_rule_based_sentiment_no_detected_keywords() -> None:
    text = "오늘 시장 거래량은 전일 대비 비슷한 수준이다"
    assert _rule_based_sentiment(text) == 0.0
