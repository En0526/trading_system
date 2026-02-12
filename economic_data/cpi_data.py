"""
CPI 相關數據獲取（前月、前年、預測值）
- 前月 / 前年：FRED API（美國勞工統計局 BLS 授權數據）
- 預測值：Trading Economics 或 Investing.com（若有 API key 或可解析）
"""
from datetime import datetime
from typing import Optional, Dict, Any
import requests
import os


# FRED 系列 ID：CPI 季調指數，可用 units 參數轉換
# units=pc1 → 較去年同期 %（YoY）
# units=pch → 月增 %（MoM）
FRED_CPI_SERIES = 'CPIAUCSL'  # Consumer Price Index for All Urban Consumers: All Items (SA)


def get_fred_api_key() -> Optional[str]:
    """取得 FRED API Key（需至 https://fredaccount.stlouisfed.org/apikeys 免費註冊）"""
    return os.environ.get('FRED_API_KEY') or os.environ.get('fred_api_key')


def fetch_cpi_from_fred() -> Dict[str, Any]:
    """
    從 FRED 取得最新 CPI 前月（MoM%）、前年（YoY%）。
    來源：Federal Reserve Economic Data (FRED)，數據來自 BLS。

    Returns:
        dict: {
            'prev_month_value': 月增率 %（字串，如 "0.2" 表示 +0.2%），
            'prev_year_value': 年增率 %（字串，如 "3.2" 表示 +3.2%），
            'source': 'FRED',
            'error': 若有錯誤則為訊息
        }
    """
    result = {'prev_month_value': None, 'prev_year_value': None, 'source': 'FRED'}
    api_key = get_fred_api_key()
    if not api_key:
        result['error'] = '未設定 FRED_API_KEY（至 https://fredaccount.stlouisfed.org/apikeys 免費註冊）'
        return result

    base_url = 'https://api.stlouisfed.org/fred/series/observations'

    try:
        # 取 MoM%（月增率）：units=pch
        params_mom = {
            'series_id': FRED_CPI_SERIES,
            'api_key': api_key,
            'file_type': 'json',
            'sort_order': 'desc',
            'limit': 2,
            'units': 'pch'  # Percent Change
        }
        r_mom = requests.get(base_url, params=params_mom, timeout=15)
        if r_mom.ok:
            data = r_mom.json()
            obs = data.get('observations', [])
            # 取最新一期（已公布）的值
            for o in obs:
                v = o.get('value', '.')
                if v and v != '.':
                    try:
                        result['prev_month_value'] = f"{float(v):.2f}%"
                        break
                    except (ValueError, TypeError):
                        pass

        # 取 YoY%（年增率）：units=pc1
        params_yoy = {
            'series_id': FRED_CPI_SERIES,
            'api_key': api_key,
            'file_type': 'json',
            'sort_order': 'desc',
            'limit': 2,
            'units': 'pc1'  # Percent Change from Year Ago
        }
        r_yoy = requests.get(base_url, params=params_yoy, timeout=15)
        if r_yoy.ok:
            data = r_yoy.json()
            obs = data.get('observations', [])
            for o in obs:
                v = o.get('value', '.')
                if v and v != '.':
                    try:
                        result['prev_year_value'] = f"{float(v):.2f}%"
                        break
                    except (ValueError, TypeError):
                        pass

    except requests.RequestException as e:
        result['error'] = f'FRED 請求失敗: {str(e)}'
    except Exception as e:
        result['error'] = f'解析 FRED 資料時發生錯誤: {str(e)}'

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
    """
    ctx = fetch_cpi_from_fred()
    forecast = fetch_cpi_forecast()
    if forecast is not None:
        ctx['forecast_value'] = forecast
    else:
        ctx['forecast_value'] = None
        ctx['forecast_hint'] = '預測值請至 Investing.com 或 Trading Economics 經濟日曆查看'
    return ctx
