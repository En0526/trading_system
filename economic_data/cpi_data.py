"""
CPI、PPI、NFP 等經濟指標前值獲取（FRED API）
需設定 FRED_API_KEY：https://fredaccount.stlouisfed.org/apikeys
"""
from datetime import datetime
from typing import Optional, Dict, Any
import requests
import os


# FRED 系列 ID
FRED_CPI_SERIES = 'CPIAUCSL'   # Consumer Price Index, All Items (SA)
FRED_PPI_SERIES = 'PPIFIS'     # Producer Price Index, Final Demand (SA)
FRED_NFP_SERIES = 'PAYEMS'     # All Employees, Total Nonfarm (千人是 Thousand Persons)


def get_fred_api_key() -> Optional[str]:
    """取得 FRED API Key（需至 https://fredaccount.stlouisfed.org/apikeys 免費註冊）"""
    return os.environ.get('FRED_API_KEY') or os.environ.get('fred_api_key')


def _fetch_fred_value(series_id: str, units: str, api_key: str) -> Optional[str]:
    """向 FRED 取單一數值，回傳字串或 None"""
    base_url = 'https://api.stlouisfed.org/fred/series/observations'
    params = {
        'series_id': series_id,
        'api_key': api_key,
        'file_type': 'json',
        'sort_order': 'desc',
        'limit': 2,
    }
    if units:
        params['units'] = units
    try:
        r = requests.get(base_url, params=params, timeout=15)
        if r.ok:
            for o in r.json().get('observations', []):
                v = o.get('value', '.')
                if v and v != '.':
                    return str(float(v))
    except Exception:
        pass
    return None


def fetch_cpi_from_fred() -> Dict[str, Any]:
    """從 FRED 取得 CPI 前月（MoM%）、前年（YoY%）"""
    result = {'prev_month_value': None, 'prev_year_value': None, 'source': 'FRED'}
    api_key = get_fred_api_key()
    if not api_key:
        result['error'] = '未設定 FRED_API_KEY（至 https://fredaccount.stlouisfed.org/apikeys 免費註冊）'
        return result
    try:
        v_mom = _fetch_fred_value(FRED_CPI_SERIES, 'pch', api_key)
        if v_mom is not None:
            result['prev_month_value'] = f"{float(v_mom):.2f}%"
        v_yoy = _fetch_fred_value(FRED_CPI_SERIES, 'pc1', api_key)
        if v_yoy is not None:
            result['prev_year_value'] = f"{float(v_yoy):.2f}%"
    except Exception as e:
        result['error'] = f'解析 FRED 資料時發生錯誤: {str(e)}'
    return result


def fetch_ppi_from_fred() -> Dict[str, Any]:
    """從 FRED 取得 PPI 前月（MoM%）、前年（YoY%）"""
    result = {'prev_month_value': None, 'prev_year_value': None, 'source': 'FRED'}
    api_key = get_fred_api_key()
    if not api_key:
        result['error'] = '未設定 FRED_API_KEY'
        return result
    try:
        v_mom = _fetch_fred_value(FRED_PPI_SERIES, 'pch', api_key)
        if v_mom is not None:
            result['prev_month_value'] = f"{float(v_mom):.2f}%"
        v_yoy = _fetch_fred_value(FRED_PPI_SERIES, 'pc1', api_key)
        if v_yoy is not None:
            result['prev_year_value'] = f"{float(v_yoy):.2f}%"
    except Exception as e:
        result['error'] = f'解析 FRED PPI 時發生錯誤: {str(e)}'
    return result


def fetch_nfp_from_fred() -> Dict[str, Any]:
    """從 FRED 取得 NFP 前月變動（千人，如 +173K）"""
    result = {'prev_month_value': None, 'prev_year_value': None, 'source': 'FRED'}
    api_key = get_fred_api_key()
    if not api_key:
        result['error'] = '未設定 FRED_API_KEY'
        return result
    try:
        # units=chg：月變動（千人）
        v_chg = _fetch_fred_value(FRED_NFP_SERIES, 'chg', api_key)
        if v_chg is not None:
            n = int(round(float(v_chg)))
            result['prev_month_value'] = f"{'+' if n >= 0 else ''}{n}K"
        # YoY 變動（千人）供參考
        v_ch1 = _fetch_fred_value(FRED_NFP_SERIES, 'ch1', api_key)
        if v_ch1 is not None:
            n = int(round(float(v_ch1)))
            result['prev_year_value'] = f"{'+' if n >= 0 else ''}{n}K"
    except Exception as e:
        result['error'] = f'解析 FRED NFP 時發生錯誤: {str(e)}'
    return result


def fetch_cpi_forecast() -> Optional[str]:
    """
    嘗試取得 CPI 預測值（共識 / consensus）。
    免費來源有限，目前回傳指引連結；若未來接入 Trading Economics 等 API 可在此擴充。

    預測值查詢來源（手動）：
    - Investing.com 經濟日曆: https://www.investing.com/economic-calendar/cpi-733
    - Trading Economics: https://tradingeconomics.com/united-states/consumer-price-index-cpi
    - Forex Factory: https://www.forexfactory.com/calendar
    """
    # 未來可擴充：Trading Economics API、或簡單爬取
    return None


def get_cpi_context() -> Dict[str, Any]:
    """
    取得 CPI 完整上下文（前月、前年、預測），供筆記 modal 使用。
    需設定 FRED_API_KEY（至 https://fredaccount.stlouisfed.org/apikeys 免費註冊）。
    """
    ctx = fetch_cpi_from_fred()
    forecast = fetch_cpi_forecast()
    if forecast is not None:
        ctx['forecast_value'] = forecast
    else:
        ctx['forecast_value'] = None
        ctx['forecast_hint'] = '預測值請至 Investing.com 或 Trading Economics 經濟日曆查看'
    return ctx
