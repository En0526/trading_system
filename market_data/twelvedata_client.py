"""
Twelve Data 貴金屬報價（期貨/現貨對應）、歷史序列
免費 8 次/分、800 次/日，需 API key：TWELVEDATA_API_KEY
"""
import os
import time
from typing import Dict, Optional
from datetime import datetime, timezone, timedelta

import requests
import pandas as pd

# Config 代碼（Yahoo 風格）-> Twelve Data 代碼（commodities / crypto）
METALS_SYMBOL_MAP = {
    "GC=F": "XAU/USD",
    "SI=F": "XAG/USD",
    "HG=F": "CX/USD",   # 銅
    "PL=F": "XPT/USD",
    "PA=F": "XPD/USD",
}
# 加密貨幣：Yahoo 格式 -> Twelve Data 格式
CRYPTO_SYMBOL_MAP = {
    "BTC-USD": "BTC/USD",
    "ETH-USD": "ETH/USD",
}


def _to_twelvedata_symbol(config_symbol: str) -> Optional[str]:
    """Config 代碼轉 Twelve Data 代碼（金屬或加密）"""
    s = METALS_SYMBOL_MAP.get(config_symbol)
    if s:
        return s
    return CRYPTO_SYMBOL_MAP.get(config_symbol)


def fetch_time_series(
    api_key: str,
    config_symbol: str,
    period: str = "20y",
) -> Optional[pd.Series]:
    """
    取得歷史收盤價序列，供比率歷史圖使用。
    period: '20y' 或 'max'（全期）
    回傳 pd.Series(index=date, values=close)，失敗回傳 None。
    """
    if not api_key or not api_key.strip():
        return None
    td_symbol = _to_twelvedata_symbol(config_symbol)
    if not td_symbol:
        return None
    end = datetime.now(timezone.utc).date()
    if period == "max":
        start = end - timedelta(days=365 * 15)  # 加密約 15 年
    else:
        start = end - timedelta(days=365 * 20)
    try:
        r = requests.get(
            "https://api.twelvedata.com/time_series",
            params={
                "symbol": td_symbol,
                "interval": "1day",
                "start_date": start.strftime("%Y-%m-%d"),
                "end_date": end.strftime("%Y-%m-%d"),
                "apikey": api_key,
                "outputsize": 5000,
            },
            timeout=20,
        )
        if r.status_code == 429:
            return None
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"TwelveData time_series {config_symbol}: {e}")
        return None
    vals = data.get("values") if isinstance(data, dict) else None
    if not vals or not isinstance(vals, list):
        return None
    rows = []
    for v in vals:
        if not isinstance(v, dict):
            continue
        dt_str = v.get("datetime")
        close_str = v.get("close")
        if not dt_str or not close_str:
            continue
        try:
            dt = pd.to_datetime(dt_str).date()
            close = float(close_str)
        except (ValueError, TypeError):
            continue
        rows.append((dt, close))
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["date", "close"])
    df = df.drop_duplicates(subset=["date"]).sort_values("date")
    # 免費方案 8 次/分，避免連續請求
    time.sleep(8)
    return pd.Series(df["close"].values, index=pd.DatetimeIndex(df["date"]))


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
