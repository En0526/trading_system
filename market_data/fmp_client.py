"""
Financial Modeling Prep API 客戶端
用於財報行事曆、美股指數報價（免費方案可用）
"""
from urllib.parse import quote
import requests
from datetime import datetime, timezone
from typing import Dict, Optional


# FMP 回傳 symbol 可能為 ^GSPC 或 GSPC，對應到我們 Config 的 key
_FMP_SYMBOL_TO_CONFIG = {
    "GSPC": "^GSPC", "DJI": "^DJI", "IXIC": "^IXIC", "NDX": "^NDX", "RUT": "^RUT",
    "^GSPC": "^GSPC", "^DJI": "^DJI", "^IXIC": "^IXIC", "^NDX": "^NDX", "^RUT": "^RUT",
}


def get_index_quotes(api_key: str, symbols: Dict[str, str]) -> Dict[str, Dict]:
    """
    美股指數報價。優先使用 FMP stable/batch-index-quotes，失敗時嘗試 v3/quote。
    symbols: Config.US_INDICES 格式 { '^GSPC': 'S&P 500', ... }
    回傳 { symbol: { current_price, change, change_percent, ... }, ... }
    """
    if not api_key or not api_key.strip() or not symbols:
        return {}
    want = set(symbols.keys())

    def _parse_response(data) -> Dict[str, Dict]:
        if isinstance(data, dict) and "data" in data:
            data = data["data"]
        if not isinstance(data, list):
            return {}
        out = {}
        for item in data:
            if not isinstance(item, dict):
                continue
            sym_raw = item.get("symbol") or ""
            sym = _FMP_SYMBOL_TO_CONFIG.get(sym_raw) or (sym_raw if sym_raw in want else None)
            if sym not in symbols:
                continue
            try:
                c = float(item.get("price", 0) or 0)
                pc = float(item.get("previousClose", c) or c)
                ch = float(item.get("changesPercentage", 0) or 0)
                change = c - pc if pc else 0
                if c <= 0:
                    continue
                out[sym] = {
                    "symbol": sym,
                    "name": symbols[sym],
                    "display_name": symbols[sym],
                    "current_price": round(c, 2),
                    "previous_close": round(pc, 2),
                    "change": round(change, 2),
                    "change_percent": round(ch, 2),
                    "volume": int(item.get("volume", 0) or 0),
                    "high": round(float(item.get("dayHigh", c)), 2) if item.get("dayHigh") else None,
                    "low": round(float(item.get("dayLow", c)), 2) if item.get("dayLow") else None,
                    "open": round(float(item.get("open", c)), 2) if item.get("open") else None,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "history": [],
                }
            except (TypeError, ValueError):
                continue
        return out

    # 1. 嘗試 stable batch-index-quotes
    for base in [
        "https://financialmodelingprep.com/stable/batch-index-quotes",
        "https://financialmodelingprep.com/api/v3/quote/" + quote(",".join(want), safe=","),
    ]:
        try:
            r = requests.get(base, params={"apikey": api_key}, timeout=12)
            if r.status_code != 200:
                continue
            data = r.json()
            out = _parse_response(data)
            if out:
                return out
        except Exception as e:
            print(f"FMP index quote ({base[:50]}...): {e}")
    return {}


def get_earnings_calendar(
    api_key: str,
    from_date: str,
    to_date: str,
    symbols_display: Dict[str, str],
) -> Dict[str, Dict]:
    """
    從 FMP 取得財報日曆。
    from_date / to_date: YYYY-MM-DD
    symbols_display: Config.US_STOCKS 格式
    回傳 { symbol: {'date': 'YYYY-MM-DD', 'days_until': int, 'name': str}, ... }
    """
    if not api_key or not api_key.strip():
        return {}
    url = "https://financialmodelingprep.com/api/v3/earning_calendar"
    try:
        r = requests.get(
            url,
            params={"from": from_date, "to": to_date, "apikey": api_key},
            timeout=15,
        )
        if r.status_code != 200:
            return {}
        data = r.json()
    except Exception as e:
        print(f"FMP earnings calendar: {e}")
        return {}
    if not isinstance(data, list):
        return {}
    today = datetime.now(timezone.utc).date()
    result = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        sym = item.get("symbol")
        d = item.get("date")
        if not sym or not d:
            continue
        # FMP 用 BRK-B，我們 key 是 BRK.B
        sym_key = sym.replace("-", ".") if "BRK" in sym.upper() else sym
        if sym_key not in symbols_display:
            continue
        try:
            ed = datetime.strptime(str(d)[:10], "%Y-%m-%d").date()
        except Exception:
            continue
        days_until = (ed - today).days
        if days_until < 0:
            continue
        if sym_key in result and result[sym_key]["date"] < str(d)[:10]:
            continue
        result[sym_key] = {
            "date": str(d)[:10],
            "days_until": days_until,
            "name": symbols_display.get(sym_key, sym_key),
        }
    return result
