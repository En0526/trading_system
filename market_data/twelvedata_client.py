"""
Twelve Data 貴金屬報價（期貨/現貨對應）
免費 8 次/分、800 次/日，需 API key：TWELVEDATA_API_KEY
"""
import os
import time
from typing import Dict, Optional
from datetime import datetime, timezone

import requests

# Config 代碼（Yahoo 風格）-> Twelve Data 代碼（commodities）
METALS_SYMBOL_MAP = {
    "GC=F": "XAU/USD",
    "SI=F": "XAG/USD",
    "HG=F": "CX/USD",   # 銅
    "PL=F": "XPT/USD",
    "PA=F": "XPD/USD",
}


def get_quote(api_key: str, symbol_twelve: str) -> Optional[Dict]:
    """單一標的報價。symbol_twelve 如 XAU/USD。回傳為通用欄位，不含 symbol/name。"""
    if not api_key or not api_key.strip():
        return None
    try:
        r = requests.get(
            "https://api.twelvedata.com/quote",
            params={"symbol": symbol_twelve, "apikey": api_key},
            timeout=10,
        )
        if r.status_code == 429:
            print(f"Twelve Data rate limit (429) for {symbol_twelve}, skip.")
            return None
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"Twelve Data quote {symbol_twelve}: {e}")
        return None
    if not isinstance(data, dict):
        return None
    try:
        close = float(data.get("close", 0))
        open_p = float(data.get("open", close))
        high = float(data.get("high", close))
        low = float(data.get("low", close))
        vol = float(data.get("volume", 0) or 0)
    except (TypeError, ValueError):
        return None
    if close == 0:
        return None
    change = close - open_p
    change_percent = (change / open_p * 100) if open_p else 0
    return {
        "current_price": round(close, 2),
        "previous_close": round(open_p, 2),
        "change": round(change, 2),
        "change_percent": round(change_percent, 2),
        "volume": int(vol),
        "high": round(high, 2),
        "low": round(low, 2),
        "open": round(open_p, 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "history": [],
    }


def get_multiple_metals(
    api_key: str,
    symbols_display: Dict[str, str],
    delay_seconds: float = 8.0,
) -> Dict[str, Dict]:
    """
    symbols_display: Config.METALS_FUTURES 格式 { 'GC=F': '黃金期貨', ... }
    依序請求，遵守 8 次/分。
    回傳 { 'GC=F': { ...market_data, symbol, name, display_name }, ... }
    """
    if not api_key or not symbols_display:
        return {}
    out = {}
    for config_key, display_name in symbols_display.items():
        sym_twelve = METALS_SYMBOL_MAP.get(config_key)
        if not sym_twelve:
            continue
        data = get_quote(api_key, sym_twelve)
        if data:
            data["symbol"] = config_key
            data["name"] = display_name
            data["display_name"] = display_name
            out[config_key] = data
        time.sleep(delay_seconds)
    return out
