"""
Financial Modeling Prep API 客戶端
用於財報行事曆等（免費方案可用）
"""
import requests
from datetime import datetime, timezone
from typing import Dict, Optional


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
