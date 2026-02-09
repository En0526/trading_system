"""
盤前資料分析模組
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import pytz
import time
from news_analysis.news_fetcher import NewsFetcher
from config import Config

class PremarketAnalyzer:
    """盤前資料分析器"""
    
    def __init__(self):
        self.news_fetcher = NewsFetcher()
        self.taiwan_tz = pytz.timezone('Asia/Taipei')
        self.us_eastern_tz = pytz.timezone('US/Eastern')
    
    def _get_taiwan_market_time(self) -> datetime:
        """獲取台灣時間"""
        return datetime.now(self.taiwan_tz)
    
    def _get_us_market_time(self) -> datetime:
        """獲取美國東部時間"""
        return datetime.now(self.us_eastern_tz)
    
    def _is_taiwan_trading_day(self, dt: datetime = None) -> bool:
        """
        判斷是否為台灣交易日
        
        Args:
            dt: 日期時間（預設為現在）
            
        Returns:
            是否為交易日
        """
        if dt is None:
            dt = self._get_taiwan_market_time()
        
        # 週六、週日不是交易日
        if dt.weekday() >= 5:  # 5=Saturday, 6=Sunday
            return False
        
        # 可以在此添加台灣假日判斷
        return True
    
    def _is_us_trading_day(self, dt: datetime = None) -> bool:
        """
        判斷是否為美國交易日
        
        Args:
            dt: 日期時間（預設為現在）
            
        Returns:
            是否為交易日
        """
        if dt is None:
            dt = self._get_us_market_time()
        
        # 週六、週日不是交易日
        if dt.weekday() >= 5:
            return False
        
        # 可以在此添加美國假日判斷
        return True
    
    def _get_last_trading_day(self, market: str = 'taiwan') -> datetime:
        """
        獲取最後一個交易日
        
        Args:
            market: 市場類型 ('taiwan' 或 'us')
            
        Returns:
            最後一個交易日的日期時間
        """
        if market == 'taiwan':
            current = self._get_taiwan_market_time()
            # 如果是週末，回退到週五
            if current.weekday() >= 5:
                days_back = current.weekday() - 4  # 週六回退1天，週日回退2天
                current = current - timedelta(days=days_back)
            return current.replace(hour=8, minute=30, second=0, microsecond=0)
        else:  # US market
            current = self._get_us_market_time()
            # 如果是週末，回退到週五
            if current.weekday() >= 5:
                days_back = current.weekday() - 4
                current = current - timedelta(days=days_back)
            # 美股開盤時間為 9:30 AM ET
            return current.replace(hour=9, minute=30, second=0, microsecond=0)
    
    def get_taiwan_premarket_news(self, force_refresh: bool = False) -> Dict:
        """
        獲取台股盤前新聞
        邏輯：如果當前時間 < 今天 8:30，顯示今天8:30的盤前資料
             如果當前時間 >= 今天 8:30，顯示今天8:30的盤前資料（保持到明天8:30）
             週末顯示上週五的盤前資料
        
        Args:
            force_refresh: 是否強制刷新（忽略緩存）
        
        Returns:
            盤前新聞分析結果
        """
        # 檢查緩存（除非強制刷新）
        cache_key = 'taiwan_premarket_news'
        if not force_refresh and hasattr(self, '_taiwan_premarket_cache'):
            cache_data = getattr(self, '_taiwan_premarket_cache', None)
            cache_time = getattr(self, '_taiwan_premarket_cache_time', 0)
            if cache_data and (time.time() - cache_time) < 3600:  # 緩存1小時
                return cache_data
        
        taiwan_time = self._get_taiwan_market_time()
        today = taiwan_time.date()
        
        # 如果是週末，使用上週五的盤前資料
        if not self._is_taiwan_trading_day():
            # 週末：使用上週五 8:30 作為基準時間
            days_back = taiwan_time.weekday() - 4  # 週六=5回退1天，週日=6回退2天
            if days_back < 0:
                days_back = 0
            last_friday = taiwan_time - timedelta(days=days_back)
            reference_time = last_friday.replace(hour=8, minute=30, second=0, microsecond=0)
            # 確保有時區信息
            if reference_time.tzinfo is None:
                reference_time = self.taiwan_tz.localize(reference_time)
            display_type = '盤前（週五）'
        else:
            # 交易日：使用今天 8:30 作為基準時間
            reference_time = taiwan_time.replace(hour=8, minute=30, second=0, microsecond=0)
            # 確保有時區信息
            if reference_time.tzinfo is None:
                reference_time = self.taiwan_tz.localize(reference_time)
            
            # 如果當前時間還沒到8:30，使用今天8:30
            # 如果當前時間已經過了8:30，也使用今天8:30（保持到明天8:30）
            if taiwan_time < reference_time:
                display_type = '盤前'
            else:
                display_type = '盤前（今日）'
        
        # 計算12小時前的時間點（從8:30往前推12小時）
        start_time = reference_time - timedelta(hours=12)
        # 確保有時區信息
        if start_time.tzinfo is None:
            start_time = self.taiwan_tz.localize(start_time)
        
        try:
            # 使用中文關鍵詞搜索台股盤前新聞（包含美股相關新聞）
            keywords = ['台股', '盤前', '美股', '美股盤後']
            news_list = self.news_fetcher.get_premarket_news(keywords, hours=12, market='taiwan')
            
            # 過濾時間範圍內的新聞（從start_time到reference_time）
            filtered_news = []
            for n in news_list:
                pub_time = n.get('published_at')
                if isinstance(pub_time, datetime):
                    # 確保時區一致（轉換為台灣時間）
                    if pub_time.tzinfo is None:
                        # 假設是 UTC 時間
                        pub_time = pub_time.replace(tzinfo=timezone.utc)
                    # 轉換為台灣時間
                    pub_time_tw = pub_time.astimezone(self.taiwan_tz)
                    
                    if start_time <= pub_time_tw <= reference_time:
                        # 更新為台灣時間
                        n['published_at'] = pub_time_tw
                        filtered_news.append(n)
            
            # 按標題排序（不區分大小寫）
            filtered_news.sort(key=lambda x: x.get('title', '').lower() if x.get('title') else '')
            
        except Exception as e:
            print(f"Error fetching Taiwan premarket news: {str(e)}")
            filtered_news = []
        
        result = {
            'market': '台股',
            'type': display_type,
            'period': '前12小時',
            'reference_time': reference_time.isoformat(),
            'start_time': start_time.isoformat(),
            'current_time': taiwan_time.isoformat(),
            'news_count': len(filtered_news),
            'news': filtered_news,  # 返回所有新聞
            'timestamp': datetime.now(self.taiwan_tz).isoformat()
        }
        
        # 更新緩存
        self._taiwan_premarket_cache = result
        self._taiwan_premarket_cache_time = time.time()
        
        return result
    
    def get_us_premarket_news(self, force_refresh: bool = False) -> Dict:
        """
        獲取美股盤前新聞
        邏輯：美股 9:30 開盤，盤前 = 開盤前 12 小時內的新聞（start_time ～ 9:30 ET）
             若當前時間 < 今天 9:30 ET，顯示「今天 9:30 的盤前」；
             若當前時間 >= 今天 9:30 ET，顯示「今天 9:30 的盤前」（維持到明日 9:30）
             週末顯示上週五的盤前資料。
        
        Args:
            force_refresh: 是否強制刷新（忽略緩存）
        
        Returns:
            盤前新聞分析結果
        """
        # 檢查緩存（除非強制刷新）
        cache_key = 'us_premarket_news'
        if not force_refresh and hasattr(self, '_us_premarket_cache'):
            cache_data = getattr(self, '_us_premarket_cache', None)
            cache_time = getattr(self, '_us_premarket_cache_time', 0)
            if cache_data and (time.time() - cache_time) < 3600:  # 緩存1小時
                return cache_data
        
        us_time = self._get_us_market_time()
        # 美股開盤時間 9:30 AM ET
        market_open_hour, market_open_minute = 9, 30
        
        # 如果是週末，使用上週五的盤前資料
        if not self._is_us_trading_day():
            days_back = us_time.weekday() - 4  # 週六=5回退1天，週日=6回退2天
            if days_back < 0:
                days_back = 0
            last_friday = us_time - timedelta(days=days_back)
            reference_time = last_friday.replace(hour=market_open_hour, minute=market_open_minute, second=0, microsecond=0)
            if reference_time.tzinfo is None:
                reference_time = self.us_eastern_tz.localize(reference_time)
            display_type = '盤前（週五）'
        else:
            reference_time = us_time.replace(hour=market_open_hour, minute=market_open_minute, second=0, microsecond=0)
            if reference_time.tzinfo is None:
                reference_time = self.us_eastern_tz.localize(reference_time)
            if us_time < reference_time:
                display_type = '盤前'
            else:
                display_type = '盤前（今日）'
        
        # 盤前 = 開盤前 12 小時內：從 reference_time - 12h 到 reference_time
        start_time = reference_time - timedelta(hours=12)
        if start_time.tzinfo is None:
            start_time = self.us_eastern_tz.localize(start_time)
        
        try:
            keywords = ['premarket', 'stock', 'market', 'earnings', 'earnings report']
            news_list = self.news_fetcher.get_premarket_news(keywords, hours=24, market='us')
            
            # 只保留「開盤前 12 小時內」的新聞：start_time <= 發佈時間 <= reference_time
            filtered_news = []
            for n in news_list:
                pub_time = n.get('published_at')
                if isinstance(pub_time, datetime):
                    if pub_time.tzinfo is None:
                        pub_time = pub_time.replace(tzinfo=timezone.utc)
                    pub_time_et = pub_time.astimezone(self.us_eastern_tz)
                    if start_time <= pub_time_et <= reference_time:
                        n['published_at'] = pub_time_et
                        filtered_news.append(n)
            
            filtered_news.sort(key=lambda x: x.get('title', '').lower() if x.get('title') else '')
            
        except Exception as e:
            print(f"Error fetching US premarket news: {str(e)}")
            filtered_news = []
        
        result = {
            'market': '美股',
            'type': display_type,
            'period': '開盤前12小時（美東9:30前）',
            'reference_time': reference_time.isoformat(),
            'start_time': start_time.isoformat(),
            'current_time': us_time.isoformat(),
            'news_count': len(filtered_news),
            'news': filtered_news,  # 返回所有新聞
            'timestamp': datetime.now(self.us_eastern_tz).isoformat()
        }
        
        # 更新緩存
        self._us_premarket_cache = result
        self._us_premarket_cache_time = time.time()
        
        return result
    
    def get_premarket_summary(self) -> Dict:
        """
        獲取盤前資料總覽（使用緩存）
        
        Returns:
            包含台股和美股盤前資料的字典
        """
        try:
            taiwan_data = self.get_taiwan_premarket_news(force_refresh=False)
        except Exception as e:
            print(f"Error getting Taiwan premarket news: {str(e)}")
            import traceback
            traceback.print_exc()
            taiwan_data = {
                'market': '台股',
                'type': '錯誤',
                'news_count': 0,
                'news': [],
                'error': str(e)
            }
        
        try:
            us_data = self.get_us_premarket_news(force_refresh=False)
        except Exception as e:
            print(f"Error getting US premarket news: {str(e)}")
            import traceback
            traceback.print_exc()
            us_data = {
                'market': '美股',
                'type': '錯誤',
                'news_count': 0,
                'news': [],
                'error': str(e)
            }
        
        return {
            'taiwan': taiwan_data,
            'us': us_data,
            'timestamp': datetime.now().isoformat()
        }

