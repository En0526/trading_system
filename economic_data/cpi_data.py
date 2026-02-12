"""
CPI、PPI、NFP、失業率、PCE、GDP 等經濟指標前值獲取（FRED API）
需設定 FRED_API_KEY：https://fredaccount.stlouisfed.org/apikeys
依發布日期判斷公佈幾月／季，前月／前年皆為對應月份／季節；前月若未公佈則不顯示。
"""
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
import requests
import os

# FRED 系列 ID
FRED_CPI_SERIES = 'CPIAUCSL'   # Consumer Price Index, All Items (SA)
FRED_PPI_SERIES = 'PPIFIS'     # Producer Price Index, Final Demand (SA)
FRED_NFP_SERIES = 'PAYEMS'     # All Employees, Total Nonfarm (千人)
FRED_UNRATE_SERIES = 'UNRATE'  # Unemployment Rate
FRED_PCE_SERIES = 'PCEPI'      # PCE Price Index (monthly)
FRED_GDP_SERIES = 'GDPC1'      # Real GDP (quarterly)


def get_fred_api_key() -> Optional[str]:
    """取得 FRED API Key（需至 https://fredaccount.stlouisfed.org/apikeys 免費註冊）"""
    return os.environ.get('FRED_API_KEY') or os.environ.get('fred_api_key')


def _obs_date_month(year: int, month: int) -> str:
    """FRED 月度 observation_date 格式：YYYY-MM-01"""
    return f"{year}-{month:02d}-01"


def _obs_date_quarter(year: int, quarter: int) -> str:
    """FRED 季度 observation_date：Q1=01-01, Q2=04-01, Q3=07-01, Q4=10-01"""
    month = (quarter - 1) * 3 + 1
    return f"{year}-{month:02d}-01"


def _fetch_fred_at_date(series_id: str, obs_date: str, units: str, api_key: str) -> Optional[str]:
    """向 FRED 取指定 observation_date 的數值。若該月／季尚未公佈則回傳 None。"""
    base_url = 'https://api.stlouisfed.org/fred/series/observations'
    params = {
        'series_id': series_id,
        'api_key': api_key,
        'file_type': 'json',
        'sort_order': 'desc',
        'limit': 1,
        'observation_end': obs_date,
        'observation_start': obs_date,
    }
    if units:
        params['units'] = units
    try:
        r = requests.get(base_url, params=params, timeout=15)
        if r.ok:
            for o in r.json().get('observations', []):
                v = o.get('value', '.')
                if v and v != '.':
                    return str(v)
    except Exception:
        pass
    return None


def get_monthly_indicator_context(
    series_id: str,
    reported_year: int,
    reported_month: int,
    units_mom: str,
    units_yoy: str,
    format_fn_mom,
    format_fn_yoy,
) -> Dict[str, Any]:
    """
    依「公佈月份」算出前月、前年同月，並向 FRED 取數值。
    reported_year, reported_month = 這次發布的數據所屬月份（例如 2 月 CPI 發布的是 1 月數據，則 reported=1 月）
    """
    result = {'prev_month_value': None, 'prev_year_value': None, 'source': 'FRED'}
    api_key = get_fred_api_key()
    if not api_key:
        result['error'] = '未設定 FRED_API_KEY'
        return result

    # 前年同月
    prev_year_month = _obs_date_month(reported_year - 1, reported_month)
    v_yoy = _fetch_fred_at_date(series_id, prev_year_month, units_yoy, api_key)
    if v_yoy is not None:
        result['prev_year_value'] = format_fn_yoy(v_yoy)

    # 前月（若該月尚未公佈，FRED 會回傳空，則不顯示）
    if reported_month == 1:
        prev_m_y, prev_m_m = reported_year - 1, 12
    else:
        prev_m_y, prev_m_m = reported_year, reported_month - 1
    prev_month_date = _obs_date_month(prev_m_y, prev_m_m)
    v_mom = _fetch_fred_at_date(series_id, prev_month_date, units_mom, api_key)
    if v_mom is not None:
        result['prev_month_value'] = format_fn_mom(v_mom)

    return result


def get_quarterly_indicator_context(
    series_id: str,
    reported_year: int,
    reported_quarter: int,
    units: str,
    format_fn,
) -> Dict[str, Any]:
    """依公佈季度算出前季、前年同季。"""
    result = {'prev_month_value': None, 'prev_year_value': None, 'source': 'FRED'}
    api_key = get_fred_api_key()
    if not api_key:
        result['error'] = '未設定 FRED_API_KEY'
        return result

    # 前年同季
    prev_y_q = _obs_date_quarter(reported_year - 1, reported_quarter)
    v_yoy = _fetch_fred_at_date(series_id, prev_y_q, units, api_key)
    if v_yoy is not None:
        result['prev_year_value'] = format_fn(v_yoy)

    # 前季
    if reported_quarter == 1:
        prev_q_y, prev_q = reported_year - 1, 4
    else:
        prev_q_y, prev_q = reported_year, reported_quarter - 1
    prev_q_date = _obs_date_quarter(prev_q_y, prev_q)
    v_mom = _fetch_fred_at_date(series_id, prev_q_date, units, api_key)
    if v_mom is not None:
        result['prev_month_value'] = format_fn(v_mom)

    return result


def infer_reported_month_from_release(release_year: int, release_month: int) -> Tuple[int, int]:
    """
    CPI/PPI：月中發布，報告的是「上月」資料（例：2 月 12 日發布 → 1 月）
    NFP/UNEMPLOYMENT：月初（第一個周五）發布，報告的是「上月」資料（例：3 月 6 日 → 2 月）
    """
    if release_month == 1:
        return release_year - 1, 12
    return release_year, release_month - 1


def fetch_cpi_for_event(reported_year: int, reported_month: int) -> Dict[str, Any]:
    """依公佈月份取得 CPI 前月（MoM%）、前年同月（YoY%）。"""
    return get_monthly_indicator_context(
        FRED_CPI_SERIES, reported_year, reported_month,
        'pch', 'pc1',
        lambda v: f"{float(v):.2f}%",
        lambda v: f"{float(v):.2f}%",
    )


def fetch_ppi_for_event(reported_year: int, reported_month: int) -> Dict[str, Any]:
    """依公佈月份取得 PPI 前月（MoM%）、前年同月（YoY%）。"""
    return get_monthly_indicator_context(
        FRED_PPI_SERIES, reported_year, reported_month,
        'pch', 'pc1',
        lambda v: f"{float(v):.2f}%",
        lambda v: f"{float(v):.2f}%",
    )


def fetch_nfp_for_event(reported_year: int, reported_month: int) -> Dict[str, Any]:
    """依公佈月份取得 NFP 前月變動（千人）、前年同月變動（千人）。"""
    result = {'prev_month_value': None, 'prev_year_value': None, 'source': 'FRED'}
    api_key = get_fred_api_key()
    if not api_key:
        result['error'] = '未設定 FRED_API_KEY'
        return result

    def fmt(v):
        n = int(round(float(v)))
        return f"{'+' if n >= 0 else ''}{n}K"

    for units, key in [('chg', 'prev_month_value'), ('ch1', 'prev_year_value')]:
        if key == 'prev_year_value':
            obs = _obs_date_month(reported_year - 1, reported_month)
        else:
            prev_m = (reported_year - 1, 12) if reported_month == 1 else (reported_year, reported_month - 1)
            obs = _obs_date_month(prev_m[0], prev_m[1])
        v = _fetch_fred_at_date(FRED_NFP_SERIES, obs, units, api_key)
        if v is not None:
            result[key] = fmt(v)

    return result


def fetch_unemployment_for_event(reported_year: int, reported_month: int) -> Dict[str, Any]:
    """依公佈月份取得失業率前月、前年同月（百分比）。UNRATE 為原始百分比，不設 units。"""
    result = {'prev_month_value': None, 'prev_year_value': None, 'source': 'FRED'}
    api_key = get_fred_api_key()
    if not api_key:
        result['error'] = '未設定 FRED_API_KEY'
        return result

    def fmt(v):
        return f"{float(v):.1f}%"

    # 前年同月
    prev_year_date = _obs_date_month(reported_year - 1, reported_month)
    v_yoy = _fetch_fred_at_date(FRED_UNRATE_SERIES, prev_year_date, '', api_key)
    if v_yoy is not None:
        result['prev_year_value'] = fmt(v_yoy)

    # 前月
    if reported_month == 1:
        prev_m_y, prev_m_m = reported_year - 1, 12
    else:
        prev_m_y, prev_m_m = reported_year, reported_month - 1
    prev_month_date = _obs_date_month(prev_m_y, prev_m_m)
    v_mom = _fetch_fred_at_date(FRED_UNRATE_SERIES, prev_month_date, '', api_key)
    if v_mom is not None:
        result['prev_month_value'] = fmt(v_mom)

    return result


def fetch_pce_for_event(reported_year: int, reported_month: int) -> Dict[str, Any]:
    """依公佈月份取得 PCE 前月（MoM%）、前年同月（YoY%）。"""
    return get_monthly_indicator_context(
        FRED_PCE_SERIES, reported_year, reported_month,
        'pch', 'pc1',
        lambda v: f"{float(v):.2f}%",
        lambda v: f"{float(v):.2f}%",
    )


def fetch_gdp_for_event(reported_year: int, reported_quarter: int) -> Dict[str, Any]:
    """依公佈季度取得 GDP 前季（QoQ%）、前年同季（YoY%）。"""
    def fmt(v):
        return f"{float(v):.2f}%"
    return get_quarterly_indicator_context(
        FRED_GDP_SERIES, reported_year, reported_quarter,
        'pch', fmt,
    )


def get_cpi_context() -> Dict[str, Any]:
    """
    取得 CPI 完整上下文（前月、前年、預測），供筆記 modal 使用。
    不使用事件時，回傳最新一筆前月／前年。
    """
    api_key = get_fred_api_key()
    result = {'prev_month_value': None, 'prev_year_value': None, 'source': 'FRED'}
    if not api_key:
        result['error'] = '未設定 FRED_API_KEY'
        return result
    base_url = 'https://api.stlouisfed.org/fred/series/observations'
    try:
        for units, key in [('pch', 'prev_month_value'), ('pc1', 'prev_year_value')]:
            params = {
                'series_id': FRED_CPI_SERIES, 'api_key': api_key, 'file_type': 'json',
                'sort_order': 'desc', 'limit': 4, 'units': units,
            }
            r = requests.get(base_url, params=params, timeout=15)
            if r.ok:
                for o in r.json().get('observations', []):
                    v = o.get('value', '.')
                    if v and v != '.':
                        result[key] = f"{float(v):.2f}%"
                        break
    except Exception:
        pass
    result['forecast_value'] = None
    result['forecast_hint'] = '預測值請至 Investing.com 或 Trading Economics 經濟日曆查看'
    return result


def get_ppi_context() -> Dict[str, Any]:
    """取得 PPI 完整上下文（前月、前年、預測），供筆記 modal 使用。"""
    api_key = get_fred_api_key()
    result = {'prev_month_value': None, 'prev_year_value': None, 'source': 'FRED'}
    if not api_key:
        result['error'] = '未設定 FRED_API_KEY'
        return result
    base_url = 'https://api.stlouisfed.org/fred/series/observations'
    try:
        for units, key in [('pch', 'prev_month_value'), ('pc1', 'prev_year_value')]:
            params = {
                'series_id': FRED_PPI_SERIES, 'api_key': api_key, 'file_type': 'json',
                'sort_order': 'desc', 'limit': 4, 'units': units,
            }
            r = requests.get(base_url, params=params, timeout=15)
            if r.ok:
                for o in r.json().get('observations', []):
                    v = o.get('value', '.')
                    if v and v != '.':
                        result[key] = f"{float(v):.2f}%"
                        break
    except Exception:
        pass
    result['forecast_value'] = None
    result['forecast_hint'] = '預測值請至 Investing.com 或 Trading Economics 經濟日曆查看'
    return result
