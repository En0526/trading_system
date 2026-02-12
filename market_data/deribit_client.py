"""
Deribit 加密貨幣報價（公開 API，無需 key）
使用交易所永續合約 ticker 或 index price
"""
from typing import Dict, Optional
from datetime import datetime, timezone

import requests

DERIBIT_API = "https://www.deribit.com/api/v2"

# Config 鍵（如 BTC-USD）-> Deribit 永續合約名稱（有則用 ticker 取得 24h 數據）
TICKER_INSTRUMENTS = {
    "BTC-USD": "BTC-PERPETUAL",
    "ETH-USD": "ETH-PERPETUAL",
    "SOL-USD": "SOL-PERPETUAL",
}
# Config 鍵 -> Deribit index_name（用於僅有 index 的幣種）
INDEX_NAMES = {
    "BTC-USD": "btc_usd",
    "ETH-USD": "eth_usd",
    "BNB-USD": "bnb_usdc",
    "XRP-USD": "xrp_usdc",
    "SOL-USD": "sol_usdt",
    "DOGE-USD": "doge_usdc",
    "ADA-USD": "ada_usdc",
    "AVAX-USD": "avax_usdc",
    "LINK-USD": "link_usdc",
}


def _get_ticker(instrument_name: str) -> Optional[Dict]:
    """取得永續合約 ticker（24h 數據）。"""
    try:
        r = requests.post(
            f"{DERIBIT_API}/public/ticker",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "public/ticker",
                "params": {"instrument_name": instrument_name},
            },
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        if "result" not in data:
            return None
        res = data["result"]
        last = res.get("last_price") or res.get("index_price")
        if last is None:
            return None
        stats = res.get("stats") or {}
        pct = stats.get("price_change")
        if pct is None:
            pct = 0
        prev = last / (1 + pct / 100) if pct else last
        return {
            "current_price": round(float(last), 2),
            "previous_close": round(float(prev), 2),
            "change": round(float(last) - float(prev), 2),
            "change_percent": round(float(pct), 2),
            "volume": int(float(stats.get("volume", 0) or 0)),
            "high": round(float(stats.get("high", last)), 2),
            "low": round(float(stats.get("low", last)), 2),
            "open": round(float(prev), 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "history": [],
        }
    except Exception as e:
        print(f"Deribit ticker {instrument_name}: {e}")
        return None


def _get_index_price(index_name: str) -> Optional[Dict]:
    """取得 index price（僅價格，無 24h 變化）。"""
    try:
        r = requests.get(
            f"{DERIBIT_API}/public/get_index_price",
            params={"index_name": index_name},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        if "result" not in data:
            return None
        price = float(data["result"].get("index_price", 0))
        if price <= 0:
            return None
        return {
            "current_price": round(price, 2),
            "previous_close": round(price, 2),
            "change": 0,
            "change_percent": 0,
            "volume": 0,
            "high": round(price, 2),
            "low": round(price, 2),
            "open": round(price, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "history": [],
        }
    except Exception as e:
        print(f"Deribit index {index_name}: {e}")
        return None


def get_single_crypto(config_key: str) -> Optional[Dict]:
    """取得單一加密貨幣報價。config_key 如 BTC-USD。"""
    inst = TICKER_INSTRUMENTS.get(config_key)
    if inst:
        out = _get_ticker(inst)
        if out:
            return out
    idx = INDEX_NAMES.get(config_key)
    if idx:
        return _get_index_price(idx)
    return None


def get_multiple_crypto(symbols_display: Dict[str, str]) -> Dict[str, Dict]:
    """
    symbols_display: Config.CRYPTO 格式 { 'BTC-USD': '比特幣', ... }
    回傳 { 'BTC-USD': { ...market_data, symbol, name, display_name }, ... }
    """
    if not symbols_display:
        return {}
    out = {}
    for config_key, display_name in symbols_display.items():
        if config_key == "USDT-USD":
            continue  # 穩定幣跳過
        data = get_single_crypto(config_key)
        if data:
            data["symbol"] = config_key
            data["name"] = display_name
            data["display_name"] = display_name
            out[config_key] = data
    return out
