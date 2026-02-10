"""
市場數據獲取模組
"""
import logging
# 抑制 yfinance 對 404 / quote not found 的日誌，避免 log 刷屏（標的仍會靜默跳過，僅回傳有資料者）
_log_yf = logging.getLogger('yfinance')
_log_yf.setLevel(logging.WARNING)
_log_yf.propagate = False

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import pytz
from config import Config

# 並行取得時每批最大執行緒數（降低可減輕單機負載與 Yahoo 壓力）
MAX_WORKERS = 8

class MarketDataFetcher:
    """市場數據獲取器"""
    
    def __init__(self):
        self.cache = {}
        self.cache_time = {}
        self.cache_duration = 120  # 緩存2分鐘，減輕重複請求
        self._earnings_cache = None
        self._earnings_cache_time = 0
        self._earnings_cache_duration = 3600 * 6  # 財報行事曆緩存 6 小時
        self._earnings_cache_tw = None
        self._earnings_cache_tw_time = 0
    
    def _is_cache_valid(self, symbol: str) -> bool:
        """檢查緩存是否有效"""
        if symbol not in self.cache_time:
            return False
        elapsed = time.time() - self.cache_time[symbol]
        return elapsed < self.cache_duration
    
    def get_market_data(self, symbol: str, period: str = '1d', interval: str = '1m') -> Optional[Dict]:
        """
        獲取市場數據
        
        Args:
            symbol: 股票代碼
            period: 時間週期 (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
            interval: 時間間隔 (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)
        
        Returns:
            包含市場數據的字典
        """
        cache_key = f"{symbol}_{period}_{interval}"
        
        # 檢查緩存
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]
        
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # 獲取歷史數據（使用2天以確保能獲取前一個交易日）
            hist = ticker.history(period='2d', interval='1d')
            # 外匯/貴金屬現貨（如 XAUUSD=X）常對 2d 無資料，改試 5d 或 1mo
            if hist.empty and ('=X' in symbol or '=x' in symbol):
                hist = ticker.history(period='5d', interval='1d')
            if hist.empty and ('=X' in symbol or '=x' in symbol):
                hist = ticker.history(period='1mo', interval='1d')
            if hist.empty:
                return None
            
            # 獲取當前價格（最新收盤價）
            current_price = hist['Close'].iloc[-1] if not hist.empty else None
            
            # 獲取前一個交易日的收盤價
            # 優先使用 info 中的 regularMarketPreviousClose
            previous_close = None
            if info and 'regularMarketPreviousClose' in info:
                previous_close = info.get('regularMarketPreviousClose')
            elif len(hist) >= 2:
                # 如果沒有，使用歷史數據中的前一個交易日
                previous_close = hist['Close'].iloc[-2]
            else:
                # 如果都沒有，使用當前價格（表示沒有變化）
                previous_close = current_price
            
            # 如果還是沒有，嘗試獲取更多歷史數據
            if previous_close is None:
                hist_longer = ticker.history(period='5d', interval='1d')
                if len(hist_longer) >= 2:
                    previous_close = hist_longer['Close'].iloc[-2]
                else:
                    previous_close = current_price
            
            # 計算變化（相對於前一個交易日的收盤價）
            if previous_close and current_price and previous_close > 0:
                change = current_price - previous_close
                change_percent = (change / previous_close) * 100
            else:
                change = 0
                change_percent = 0
            
            # 獲取今日數據（使用最新的數據）
            hist_today = ticker.history(period='1d', interval='1m')
            if not hist_today.empty:
                today_data = hist_today.iloc[-1]
            else:
                # 如果沒有分鐘數據，使用日數據
                today_data = hist.iloc[-1] if not hist.empty else None
            
            # 獲取今日開盤、最高、最低、成交量
            open_price = None
            high_price = None
            low_price = None
            volume = 0
            
            if today_data is not None:
                try:
                    open_price = float(today_data.get('Open', today_data['Open']))
                    high_price = float(today_data.get('High', today_data['High']))
                    low_price = float(today_data.get('Low', today_data['Low']))
                    volume = int(today_data.get('Volume', today_data['Volume']))
                except (KeyError, TypeError, ValueError):
                    pass
            
            # 如果沒有今日數據，嘗試從 info 獲取
            if open_price is None and info:
                open_price = info.get('regularMarketOpen') or info.get('open')
            if high_price is None and info:
                high_price = info.get('regularMarketDayHigh') or info.get('dayHigh')
            if low_price is None and info:
                low_price = info.get('regularMarketDayLow') or info.get('dayLow')
            if volume == 0 and info:
                volume = info.get('regularMarketVolume') or info.get('volume') or 0
            
            # 如果還是沒有，使用當前價格作為備用
            if open_price is None:
                open_price = current_price
            if high_price is None:
                high_price = current_price
            if low_price is None:
                low_price = current_price
            
            result = {
                'symbol': symbol,
                'name': info.get('longName') or info.get('shortName') or symbol,
                'current_price': round(current_price, 2) if current_price else None,
                'previous_close': round(previous_close, 2) if previous_close else None,
                'change': round(change, 2),
                'change_percent': round(change_percent, 2),
                'volume': int(volume) if volume else 0,
                'high': round(high_price, 2) if high_price else None,
                'low': round(low_price, 2) if low_price else None,
                'open': round(open_price, 2) if open_price else None,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'history': hist.to_dict('records') if not hist.empty else []
            }
            
            # 更新緩存
            self.cache[cache_key] = result
            self.cache_time[cache_key] = time.time()
            
            return result
            
        except Exception as e:
            print(f"Error fetching data for {symbol}: {str(e)}")
            return None
    
    def get_multiple_markets(self, symbols: Dict[str, str], period: str = '1d') -> Dict[str, Dict]:
        """
        批量獲取多個市場數據（並行請求，加快速度）
        """
        if not symbols:
            return {}
        results = {}
        items = list(symbols.items())
        n = min(MAX_WORKERS, len(items))

        def fetch_one(item):
            symbol, name = item
            data = self.get_market_data(symbol, period=period)
            if data:
                data = dict(data)
                data['display_name'] = name
                return (symbol, data)
            return (symbol, None)

        with ThreadPoolExecutor(max_workers=n) as executor:
            for future in as_completed(executor.submit(fetch_one, item) for item in items):
                try:
                    symbol, data = future.result()
                    if data:
                        results[symbol] = data
                except Exception:
                    pass
        return results

    def _fetch_hist(self, symbol: str, period: str = '20y') -> Optional[pd.Series]:
        """取得收盤價歷史序列，用於計算比率。"""
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval='1d')
            if df is None or df.empty or 'Close' not in df.columns:
                return None
            return df['Close'].dropna()
        except Exception as e:
            print(f"Error fetching history for {symbol}: {e}")
            return None

    def _normalize_series_index(self, series: pd.Series) -> pd.Series:
        """將指數正規化為「日期 only」、無時區，以便與其他標的對齊（避免 BTC 與 GC=F 時區不同導致交集為空）。"""
        if series is None or series.empty:
            return series
        idx = pd.to_datetime(series.index)
        if idx.tz is not None:
            idx = idx.tz_localize(None)
        idx = idx.normalize()
        series = series.copy()
        series.index = idx
        if series.index.duplicated().any():
            series = series.groupby(series.index).last()
        return series

    def _compute_one_ratio(self, defn: dict) -> dict:
        """計算單一比率：當前值、區間最高、最低。"""
        rid = defn.get('id', '')
        name = defn.get('name', rid)
        num_sym = defn.get('num', '')
        denom_sym = defn.get('denom', '')
        period = defn.get('period', '20y')
        unit = defn.get('unit', '倍')
        desc = defn.get('desc', '')
        num_series = self._fetch_hist(num_sym, period)
        time.sleep(0.15)
        denom_series = self._fetch_hist(denom_sym, period)
        if num_series is None or denom_series is None:
            return {
                'id': rid,
                'name': name,
                'description': desc,
                'unit': unit,
                'current': None,
                'range_high': None,
                'range_low': None,
                'period_label': '20年' if period == '20y' else '全期',
                'error': '缺少價格資料',
            }
        # 正規化 index（日期 only），避免加密與期貨時區不同導致交集為空（如 BTC 黃金比）
        num_series = self._normalize_series_index(num_series)
        denom_series = self._normalize_series_index(denom_series)
        if num_series.empty or denom_series.empty:
            return {
                'id': rid,
                'name': name,
                'description': desc,
                'unit': unit,
                'current': None,
                'range_high': None,
                'range_low': None,
                'period_label': '20年' if period == '20y' else '全期',
                'error': '缺少價格資料',
            }
        # 對齊日期（取交集）
        common = num_series.index.intersection(denom_series.index)
        if len(common) == 0:
            return {
                'id': rid,
                'name': name,
                'description': desc,
                'unit': unit,
                'current': None,
                'range_high': None,
                'range_low': None,
                'period_label': '20年' if period == '20y' else '全期',
                'error': '無重疊交易日',
            }
        num_aligned = num_series.reindex(common).ffill().bfill()
        denom_aligned = denom_series.reindex(common).ffill().bfill()
        valid = (num_aligned > 0) & (denom_aligned > 0)
        if not valid.any():
            return {
                'id': rid,
                'name': name,
                'description': desc,
                'unit': unit,
                'current': None,
                'range_high': None,
                'range_low': None,
                'period_label': '20年' if period == '20y' else '全期',
                'error': '無有效比率',
            }
        ratio_series = num_aligned / denom_aligned
        ratio_series = ratio_series[valid]
        current = float(ratio_series.iloc[-1]) if len(ratio_series) else None
        range_high = float(ratio_series.max()) if len(ratio_series) else None
        range_low = float(ratio_series.min()) if len(ratio_series) else None
        return {
            'id': rid,
            'name': name,
            'description': desc,
            'unit': unit,
            'current': round(current, 4) if current is not None else None,
            'range_high': round(range_high, 4) if range_high is not None else None,
            'range_low': round(range_low, 4) if range_low is not None else None,
            'period_label': '20年' if period == '20y' else '全期',
            'error': None,
        }

    def get_ratios_summary(self, force_refresh: bool = False) -> dict:
        """
        取得所有重要比率：當前值、20年（或全期）最高/最低。
        結果緩存 60 秒，force_refresh 時忽略緩存。
        """
        cache_key = 'ratios_summary'
        if not force_refresh and self._is_cache_valid(cache_key):
            return self.cache[cache_key]
        definitions = getattr(Config, 'RATIO_DEFINITIONS', [])
        ratios = []
        for defn in definitions:
            r = self._compute_one_ratio(defn)
            ratios.append(r)
            time.sleep(0.1)
        out = {
            'ratios': ratios,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
        self.cache[cache_key] = out
        self.cache_time[cache_key] = time.time()
        return out

    def get_ratio_history(self, ratio_id: str, resample: str = '1M') -> Optional[dict]:
        """
        取得單一比率的歷史序列，供走勢圖使用。
        resample: '1M'=月線(約240點/20年)，'1W'=週線，'1d'=日線(資料量大)。
        """
        definitions = getattr(Config, 'RATIO_DEFINITIONS', [])
        defn = next((d for d in definitions if d.get('id') == ratio_id), None)
        if not defn:
            return None
        num_sym = defn.get('num', '')
        denom_sym = defn.get('denom', '')
        period = defn.get('period', '20y')
        num_series = self._fetch_hist(num_sym, period)
        time.sleep(0.15)
        denom_series = self._fetch_hist(denom_sym, period)
        if num_series is None or denom_series is None:
            return None
        # 正規化 index（日期 only、無時區），否則 BTC-USD 與 GC=F 時區不同會導致 intersection 為空
        num_series = self._normalize_series_index(num_series)
        denom_series = self._normalize_series_index(denom_series)
        if num_series is None or num_series.empty or denom_series is None or denom_series.empty:
            return None
        common = num_series.index.intersection(denom_series.index)
        if len(common) == 0:
            return None
        num_aligned = num_series.reindex(common).ffill().bfill()
        denom_aligned = denom_series.reindex(common).ffill().bfill()
        valid = (num_aligned > 0) & (denom_aligned > 0)
        if not valid.any():
            return None
        ratio_series = (num_aligned / denom_aligned)[valid]
        if resample and resample != '1d':
            # 月線用 'M'（pandas 月尾），避免 '1M' 被當成 1 分鐘
            rule = 'M' if resample == '1M' else resample
            ratio_series = ratio_series.resample(rule).last().dropna()
        dates = [d.strftime('%Y-%m-%d') for d in ratio_series.index]
        values = [round(float(v), 4) for v in ratio_series.values]
        return {
            'id': ratio_id,
            'name': defn.get('name', ratio_id),
            'period_label': '20年' if period == '20y' else '全期',
            'dates': dates,
            'values': values,
        }

    def get_earnings_calendar(self, days_ahead: int = 60, force_refresh: bool = False) -> Dict[str, Dict]:
        """
        取得美股接下來 N 天內的財報公布日（依 Config.US_STOCKS）。
        回傳 { symbol: {'date': 'YYYY-MM-DD', 'days_until': int, 'name': str}, ... }
        """
        now = time.time()
        if not force_refresh and self._earnings_cache is not None and (now - self._earnings_cache_time) < self._earnings_cache_duration:
            return self._earnings_cache
        try:
            tz_et = pytz.timezone('US/Eastern')
            today = datetime.now(tz_et).date()
            end_date = today + timedelta(days=days_ahead)
            result = {}
            for symbol, name in Config.US_STOCKS.items():
                try:
                    ticker = yf.Ticker(symbol)
                    ed = ticker.get_earnings_dates()
                    if ed is None or ed.empty:
                        continue
                    # 指數為財報日（可能帶時區）
                    dates = ed.index
                    next_date = None
                    for d in dates:
                        try:
                            ts = pd.Timestamp(d)
                            if ts.tz is not None:
                                ts = ts.tz_convert(tz_et)
                            d_date = ts.date()
                        except Exception:
                            continue
                        if today <= d_date <= end_date:
                            if next_date is None or d_date < next_date:
                                next_date = d_date
                    if next_date is not None:
                        days_until = (next_date - today).days
                        result[symbol] = {
                            'date': next_date.strftime('%Y-%m-%d'),
                            'days_until': days_until,
                            'name': name,
                        }
                    time.sleep(0.12)
                except Exception as e:
                    print(f"Earnings date fetch skip {symbol}: {e}")
                    continue
            self._earnings_cache = result
            self._earnings_cache_time = now
            return result
        except Exception as e:
            print(f"get_earnings_calendar error: {e}")
            return self._earnings_cache or {}

    def get_earnings_calendar_tw(self, days_ahead: int = 60, force_refresh: bool = False) -> Dict[str, Dict]:
        """
        取得台股接下來 N 天內的財報公布日（依 Config.TW_MARKETS，排除指數如 ^TWII）。
        資料來源同美股：yfinance（Yahoo Finance），台股代碼為 .TW。
        回傳 { symbol: {'date': 'YYYY-MM-DD', 'days_until': int, 'name': str}, ... }
        """
        now = time.time()
        if not force_refresh and self._earnings_cache_tw is not None and (now - self._earnings_cache_tw_time) < self._earnings_cache_duration:
            return self._earnings_cache_tw
        try:
            tz_tw = pytz.timezone('Asia/Taipei')
            today = datetime.now(tz_tw).date()
            end_date = today + timedelta(days=days_ahead)
            result = {}
            for symbol, name in Config.TW_MARKETS.items():
                if symbol.startswith('^'):
                    continue  # 跳過指數
                try:
                    ticker = yf.Ticker(symbol)
                    ed = ticker.get_earnings_dates()
                    if ed is None or ed.empty:
                        continue
                    dates = ed.index
                    next_date = None
                    for d in dates:
                        try:
                            ts = pd.Timestamp(d)
                            if ts.tz is not None:
                                ts = ts.tz_convert(tz_tw)
                            d_date = ts.date()
                        except Exception:
                            continue
                        if today <= d_date <= end_date:
                            if next_date is None or d_date < next_date:
                                next_date = d_date
                    if next_date is not None:
                        days_until = (next_date - today).days
                        result[symbol] = {
                            'date': next_date.strftime('%Y-%m-%d'),
                            'days_until': days_until,
                            'name': name,
                        }
                    time.sleep(0.12)
                except Exception as e:
                    print(f"Earnings date fetch skip {symbol}: {e}")
                    continue
            self._earnings_cache_tw = result
            self._earnings_cache_tw_time = now
            return result
        except Exception as e:
            print(f"get_earnings_calendar_tw error: {e}")
            return self._earnings_cache_tw or {}

    def _get_comex_session(self) -> str:
        """
        依美東時間判斷 COMEX 期貨目前為日盤或夜盤。
        日盤（Regular）：週一至五 8:20 - 13:30 ET
        其餘為夜盤（電子盤）。
        """
        try:
            et = datetime.now(pytz.timezone('US/Eastern'))
            # 週末視為夜盤
            if et.weekday() >= 5:
                return '夜盤'
            hour, minute = et.hour, et.minute
            t = hour * 60 + minute
            # 8:20 = 500 分, 13:30 = 810 分
            if 500 <= t < 810:
                return '日盤'
            return '夜盤'
        except Exception:
            return '—'

    def get_stock_history(self, symbol: str, period: str = '1y') -> Optional[Dict]:
        """
        取得單一標的過去一段時間的收盤價歷史，供走勢圖使用（點擊卡片時才拉取，不拖慢首屏）。
        period: 1y, 6mo, 3mo 等（yfinance 格式）
        """
        cache_key = f"hist_{symbol}_{period}"
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval='1d')
            if df is None or df.empty or 'Close' not in df.columns:
                return None
            series = df['Close'].dropna()
            if series.empty:
                return None
            series = self._normalize_series_index(series)
            dates = [d.strftime('%Y-%m-%d') for d in series.index]
            values = [round(float(v), 2) for v in series.values]
            info = getattr(ticker, 'info', None) or {}
            name = (info.get('longName') or info.get('shortName') or symbol)
            if isinstance(name, str):
                name = name.strip() or symbol
            else:
                name = symbol
            out = {
                'symbol': symbol,
                'name': name,
                'period': period,
                'dates': dates,
                'values': values,
            }
            self.cache[cache_key] = out
            self.cache_time[cache_key] = time.time()
            return out
        except Exception as e:
            print(f"Error fetching stock history for {symbol}: {e}")
            return None

    def get_market_summary(self, sections: Optional[List[str]] = None) -> Dict:
        """
        獲取市場總覽（美股／台股／國際／重金屬／加密等並行取得，加快速度）。
        sections: 若提供則只取得指定區塊（例：['us_indices','us_stocks']），首屏可先取 us_indices 加快顯示。
        """
        session = self._get_comex_session()
        try:
            et_now = datetime.now(pytz.timezone('US/Eastern'))
            metals_session_et = et_now.strftime('%H:%M')
        except Exception:
            metals_session_et = ''

        all_tasks = {
            'metals_futures_raw': lambda: self.get_multiple_markets(getattr(Config, 'METALS_FUTURES', {})),
            'crypto': lambda: self.get_multiple_markets(getattr(Config, 'CRYPTO', {})),
            'us_stocks': lambda: self.get_multiple_markets(Config.US_STOCKS),
            'tw_markets': lambda: self.get_multiple_markets(Config.TW_MARKETS),
            'us_indices': lambda: self.get_multiple_markets(Config.US_INDICES),
            'international_markets': lambda: self.get_multiple_markets(Config.INTERNATIONAL_MARKETS),
            'ratios': lambda: self.get_ratios_summary(),
        }
        if sections is not None:
            # 前端指定區塊時只跑這些（metals_futures 對應 metals_futures_raw）
            allowed = set(sections)
            if 'metals_futures' in allowed:
                allowed.add('metals_futures_raw')
                allowed.discard('metals_futures')
            tasks = {k: v for k, v in all_tasks.items() if k in allowed}
        else:
            tasks = all_tasks

        out = {}
        with ThreadPoolExecutor(max_workers=min(8, len(tasks))) as executor:
            f2k = {executor.submit(fn): k for k, fn in tasks.items()}
            for future in as_completed(f2k):
                k = f2k[future]
                try:
                    out[k] = future.result()
                except Exception:
                    if k == 'ratios':
                        out[k] = {'ratios': [], 'timestamp': datetime.now(timezone.utc).isoformat()}
                    else:
                        out[k] = {} if k != 'metals_futures_raw' else {}

        metals_futures_raw = out.get('metals_futures_raw', {})
        metals_futures = {sym: dict(d, session=session) for sym, d in metals_futures_raw.items()}
        crypto = out.get('crypto', {})
        us_stocks = out.get('us_stocks', {})
        tw_markets = out.get('tw_markets', {})
        us_indices = out.get('us_indices', {})
        international_markets = out.get('international_markets', {})
        ratios_data = out.get('ratios') or (self.get_ratios_summary() if (sections is None or 'ratios' in (sections or [])) else {})

        earnings_list = []
        if us_stocks and (sections is None or 'us_stocks' in sections):
            earnings_cal = self.get_earnings_calendar(days_ahead=60)
            for symbol, data in us_stocks.items():
                if symbol in earnings_cal:
                    ec = earnings_cal[symbol]
                    data['earnings_date'] = ec['date']
                    data['earnings_days_until'] = ec['days_until']
                    earnings_list.append({
                        'symbol': symbol,
                        'name': data.get('display_name') or data.get('name') or ec.get('name', symbol),
                        'date': ec['date'],
                        'days_until': ec['days_until'],
                    })
            earnings_list.sort(key=lambda x: (x['date'], x['symbol']))

        earnings_list_tw = []
        if tw_markets and (sections is None or 'tw_markets' in sections):
            earnings_cal_tw = self.get_earnings_calendar_tw(days_ahead=60)
            for symbol, data in tw_markets.items():
                if symbol in earnings_cal_tw:
                    ec = earnings_cal_tw[symbol]
                    data['earnings_date'] = ec['date']
                    data['earnings_days_until'] = ec['days_until']
                    earnings_list_tw.append({
                        'symbol': symbol,
                        'name': data.get('display_name') or data.get('name') or ec.get('name', symbol),
                        'date': ec['date'],
                        'days_until': ec['days_until'],
                    })
            earnings_list_tw.sort(key=lambda x: (x['date'], x['symbol']))

        summary = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
        if sections is None or 'ratios' in sections:
            summary['ratios'] = ratios_data
        if sections is None or 'us_indices' in sections:
            summary['us_indices'] = us_indices
        if sections is None or 'us_stocks' in sections:
            summary['us_stocks'] = us_stocks
            summary['earnings_upcoming'] = earnings_list
        if sections is None or 'tw_markets' in sections:
            summary['tw_markets'] = tw_markets
            summary['earnings_upcoming_tw'] = earnings_list_tw
        if sections is None or 'international_markets' in sections:
            summary['international_markets'] = international_markets
        if sections is None or 'metals_futures' in sections or 'metals_futures_raw' in (out or {}):
            summary['metals_futures'] = metals_futures
            summary['metals_session'] = session
            summary['metals_session_et'] = metals_session_et
        if sections is None or 'crypto' in sections:
            summary['crypto'] = crypto

        # 回傳「有請求但無資料」的標的，方便比對是否代碼錯誤或環境差異（如 Render 與本機）
        section_to_config = {
            'us_indices': getattr(Config, 'US_INDICES', {}),
            'us_stocks': getattr(Config, 'US_STOCKS', {}),
            'tw_markets': getattr(Config, 'TW_MARKETS', {}),
            'international_markets': getattr(Config, 'INTERNATIONAL_MARKETS', {}),
            'metals_futures': getattr(Config, 'METALS_FUTURES', {}),
            'crypto': getattr(Config, 'CRYPTO', {}),
        }
        skipped_symbols = []
        for sec, config_dict in section_to_config.items():
            result_dict = summary.get(sec)
            if not isinstance(config_dict, dict) or not isinstance(result_dict, dict):
                continue
            requested = set(config_dict.keys())
            got = set(result_dict.keys())
            for sym in requested - got:
                skipped_symbols.append({
                    'symbol': sym,
                    'section': sec,
                    'name': config_dict.get(sym, sym),
                })
        summary['skipped_symbols'] = skipped_symbols
        return summary

