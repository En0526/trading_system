"""
Finnhub 美股報價（美股、美股指數）
免費 60 次/分，需 API key：FINNHUB_API_KEY
"""
import os
import time
from typing import Dict, Optional
from datetime import datetime, timezone

import requests

# Finnhub 用 - 取代 . 如 BRK.B -> BRK-B；指數用 .SPX 等
FINNHUB_INDEX_MAP = {
    "^GSPC": ".SPX",
    "^DJI": ".DJI",
    "^IXIC": ".IXIC",
}


def _finnhub_symbol(symbol: str) -> str:
    if not isinstance(symbol, str):
        return symbol
    if symbol in FINNHUB_INDEX_MAP:
        return FINNHUB_INDEX_MAP[symbol]
    return symbol.replace(".", "-")


def get_quote(api_key: str, symbol: str, display_name: str) -> Optional[Dict]:
    """
    取得單一標的報價，回傳與 data_fetcher.get_market_data 相容的格式。
    symbol: 如 AAPL, ^GSPC（Finnhub 可能接受或需對應 .SPX 等）
    """
    if not api_key or api_key.strip() == "":
        return None
    sym = _finnhub_symbol(symbol)
    url = "https://finnhub.io/api/v1/quote"
    try:
        r = requests.get(url, params={"symbol": sym, "token": api_key}, timeout=10)
        if r.status_code == 429:
            print(f"Finnhub rate limit (429) for {symbol}, skip.")
            return None
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"Finnhub quote {symbol}: {e}")
        return None
    c = data.get("c")  # current
    pc = data.get("pc")  # previous close
    if c is None:
        return None
    try:
        current = float(c)
        prev = float(pc) if pc is not None else current
    except (TypeError, ValueError):
        return None
    change = current - prev if prev else 0
    change_percent = (change / prev * 100) if prev and prev != 0 else 0
    o = data.get("o")
    h = data.get("h")
    l = data.get("l")
    v = data.get("v") or 0
    return {
        "symbol": symbol,
        "name": display_name,
        "current_price": round(current, 2),
        "previous_close": round(prev, 2),
        "change": round(change, 2),
        "change_percent": round(change_percent, 2),
        "volume": int(v) if v is not None else 0,
        "high": round(float(h), 2) if h is not None else None,
        "low": round(float(l), 2) if l is not None else None,
        "open": round(float(o), 2) if o is not None else None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "history": [],
    }


def get_multiple_quotes(
    api_key: str,
    symbols: Dict[str, str],
    delay_seconds: float = 1.05,
) -> Dict[str, Dict]:
    """
    依序取得多個標的（遵守 60 次/分 ≈ 每請求間隔 1 秒）。
    回傳 { symbol: { ...market_data }, ... }
    """
    if not api_key or not symbols:
        return {}
    out = {}
    for symbol, name in symbols.items():
        d = get_quote(api_key, symbol, name)
        if d:
            d["display_name"] = name
            out[symbol] = d
        time.sleep(delay_seconds)
    return out
