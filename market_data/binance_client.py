"""
幣安 Binance 加密貨幣報價（公開 API，無需 key）
"""
from typing import Dict, Optional
from datetime import datetime, timezone

import requests

# Config 鍵（如 BTC-USD）-> Binance 交易對
def _to_binance_symbol(config_key: str) -> str:
    if not config_key or "-USD" not in config_key.upper():
        return config_key.replace("-", "") + "USDT"
    return config_key.replace("-USD", "USDT").replace("-", "")


def get_ticker_24h(binance_symbol: str) -> Optional[Dict]:
    """單一交易對 24h 報價。binance_symbol 如 BTCUSDT。"""
    try:
        r = requests.get(
            "https://api.binance.com/api/v3/ticker/24hr",
            params={"symbol": binance_symbol},
            timeout=10,
        )
        if r.status_code == 429:
            print(f"Binance rate limit (429) for {binance_symbol}, skip.")
            return None
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"Binance ticker {binance_symbol}: {e}")
        return None
    try:
        last = float(data.get("lastPrice", 0))
        open_p = float(data.get("openPrice", last))
        high = float(data.get("highPrice", last))
        low = float(data.get("lowPrice", last))
        vol = float(data.get("volume", 0))
        pct = float(data.get("priceChangePercent", 0))
        change = float(data.get("priceChange", 0))
    except (TypeError, ValueError):
        return None
    if last == 0:
        return None
    return {
        "current_price": round(last, 2),
        "previous_close": round(open_p, 2),
        "change": round(change, 2),
        "change_percent": round(pct, 2),
        "volume": int(vol),
        "high": round(high, 2),
        "low": round(low, 2),
        "open": round(open_p, 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "history": [],
    }


def get_multiple_crypto(
    symbols_display: Dict[str, str],
) -> Dict[str, Dict]:
    """
    symbols_display: Config.CRYPTO 格式 { 'BTC-USD': '比特幣', ... }
    回傳 { 'BTC-USD': { ...market_data, symbol, name, display_name }, ... }
    """
    if not symbols_display:
        return {}
    out = {}
    for config_key, display_name in symbols_display.items():
        sym = _to_binance_symbol(config_key)
        data = get_ticker_24h(sym)
        if data:
            data["symbol"] = config_key
            data["name"] = display_name
            data["display_name"] = display_name
            out[config_key] = data
    return out
