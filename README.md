# Auto Trading (Safe Defaults)

간단한 FastAPI 기반 자동매매 백엔드 스켈레톤입니다.

## 로컬 실행

```bash
python -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn requests
uvicorn app.main:app --reload
```

## 기본 환경변수

`app/config.py`는 아래 값을 기본값으로 사용합니다.

- `PAPER_TRADING_ENABLED=true`
- `ENABLE_LIVE_TRADING=false`
- `PAPER_TRADING_INITIAL_CASH=1000000`
- `COMMISSION_RATE=0.00015`
- `TAX_RATE=0.0018`
- `SQLITE_DB_PATH=trading.db`

필요 시 실행 전에 환경변수로 재정의할 수 있습니다.

## 안전 가드 (Startup Safety Guard)

앱 시작 시 `PAPER_TRADING_ENABLED`와 `ENABLE_LIVE_TRADING`가 동시에 `true`이면
`RuntimeError`를 발생시키고 서버 기동을 중단합니다.

예시:

```bash
export PAPER_TRADING_ENABLED=true
export ENABLE_LIVE_TRADING=true
uvicorn app.main:app --reload
# -> RuntimeError: Unsafe startup blocked ...
```

## 기본 API

- `GET /health`
- `GET /news`
- `GET /news/{symbol}`
- `GET /news/score/{symbol}`
- `POST /news/collect`
- `GET /paper/account`
- `GET /paper/positions`
- `GET /paper/report`
- `POST /paper/reset`
