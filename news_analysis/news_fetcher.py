"""
新聞數據獲取模組 - 從新聞網站抓取
"""
import requests
from bs4 import BeautifulSoup
import feedparser
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import time
import re
from collections import Counter
from urllib.parse import quote_plus
from config import Config

class NewsFetcher:
    """新聞數據獲取器 - 從新聞網站抓取"""
    
    def __init__(self):
        self.cache = {}
        self.cache_time = {}
        self.cache_duration = 600  # 緩存10分鐘，減輕算力
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
    def _is_cache_valid(self, key: str) -> bool:
        """檢查緩存是否有效"""
        if key not in self.cache_time:
            return False
        elapsed = time.time() - self.cache_time[key]
        return elapsed < self.cache_duration
    
    def _parse_datetime(self, date_str: str, default_tz=None) -> Optional[datetime]:
        """解析日期時間字符串"""
        if not date_str:
            return None
        
        # 嘗試多種日期格式
        formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y/%m/%d %H:%M:%S',
            '%Y/%m/%d %H:%M',
            '%Y-%m-%d',
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                if default_tz:
                    if dt.tzinfo is None:
                        dt = default_tz.localize(dt)
                return dt
            except:
                continue
        
        return None
    
    def fetch_from_rss(self, rss_url: str, keywords: List[str] = None, hours: int = 12, filter_keywords: bool = True) -> List[Dict]:
        """
        從 RSS Feed 獲取新聞
        
        Args:
            rss_url: RSS Feed URL
            keywords: 關鍵詞列表（用於過濾，如果 filter_keywords=False 則不過濾）
            hours: 時間範圍（小時）
            filter_keywords: 是否進行關鍵詞過濾（預設True，RSS源通常設為False）
            
        Returns:
            新聞列表
        """
        news_list = []
        # 使用 UTC 時區的 cutoff_time
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        try:
            feed = feedparser.parse(rss_url)
            
            for entry in feed.entries:
                title = entry.get('title', '')
                link = entry.get('link', '')
                summary = entry.get('summary', '')
                
                # 關鍵詞過濾（只有當 filter_keywords=True 時才過濾）
                # RSS源（如鉅亨、經濟日報）本身就是台股新聞，不需要過濾
                if filter_keywords and keywords:
                    text = (title + ' ' + summary).lower()
                    if not any(keyword.lower() in text for keyword in keywords):
                        continue
                
                # 解析時間
                pub_time = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    pub_time = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                elif hasattr(entry, 'published'):
                    pub_time = self._parse_datetime(entry.published)
                    if pub_time and pub_time.tzinfo is None:
                        pub_time = pub_time.replace(tzinfo=timezone.utc)
                
                if not pub_time:
                    pub_time = datetime.now(timezone.utc)
                elif pub_time.tzinfo is None:
                    # 如果沒有時區信息，假設是 UTC
                    pub_time = pub_time.replace(tzinfo=timezone.utc)
                
                # 時間過濾（確保都是 aware datetime）
                if pub_time < cutoff_time:
                    continue
                
                # 過濾 Facebook 新聞（先檢查連結）
                if 'facebook.com' in link.lower() or 'fb.com' in link.lower():
                    continue
                
                # 獲取發布者
                publisher = entry.get('source', {}).get('title', '') if hasattr(entry, 'source') else ''
                if not publisher:
                    # 從 URL 推斷發布者
                    if 'cnyes.com' in link or 'cnyes' in link:
                        publisher = '鉅亨網'
                    elif 'udn.com' in link or 'money.udn' in link:
                        publisher = '經濟日報'
                    elif 'yahoo.com' in link or 'yahoo' in link:
                        publisher = 'Yahoo 財經'
                    elif 'wsj.com' in link or 'wsj' in link or 'wallstreetjournal' in link:
                        publisher = 'Wall Street Journal'
                    elif 'reuters.com' in link:
                        publisher = 'Reuters'
                    elif 'bloomberg.com' in link:
                        publisher = 'Bloomberg'
                    else:
                        publisher = 'Unknown'
                
                # 再次檢查發布者是否為 Facebook
                if 'facebook' in publisher.lower():
                    continue
                
                news_list.append({
                    'title': title,
                    'publisher': publisher,
                    'link': link,
                    'published_at': pub_time,
                    'summary': summary,
                    'source': 'rss'
                })
                
        except Exception as e:
            print(f"Error fetching RSS from {rss_url}: {str(e)}")
        
        return news_list
    
    def fetch_from_google_news(self, keywords: List[str], hours: int = 12, language: str = 'zh-TW', region: str = 'TW') -> List[Dict]:
        """
        從 Google News RSS 獲取新聞
        
        Args:
            keywords: 關鍵詞列表
            hours: 時間範圍（小時）
            language: 語言代碼
            region: 地區代碼
            
        Returns:
            新聞列表
        """
        # Google News RSS URL (需要 URL 編碼)
        query = '+'.join([quote_plus(k) for k in keywords])
        if region == 'US':
            rss_url = f"https://news.google.com/rss/search?q={query}&hl=en&gl=US&ceid=US:en"
        else:
            rss_url = f"https://news.google.com/rss/search?q={query}&hl={language}&gl={region}&ceid={region}:{language}"
        
        return self.fetch_from_rss(rss_url, keywords, hours)
    
    def get_premarket_news(self, keywords: List[str], hours: int = 12, market: str = 'taiwan') -> List[Dict]:
        """
        獲取盤前新聞（使用關鍵詞搜索，每個關鍵詞單獨搜索）
        
        Args:
            keywords: 關鍵詞列表（例如：['台股', '盤前', '美股', '美股盤後']）
            hours: 時間範圍（小時，預設12小時）
            market: 市場類型 ('taiwan' 或 'us')
            
        Returns:
            新聞列表
        """
        cache_key = f"premarket_{market}_{'_'.join(keywords)}_{hours}"
        
        # 檢查緩存
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]
        
        all_news = []
        # 使用 UTC 時區的 cutoff_time
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        if market == 'taiwan':
            # 台股新聞來源 - 每個關鍵詞單獨搜索
            # 優先順序：鉅亨、經濟日報、Yahoo、Wall Street Journal、Google News
            
            # 為每個關鍵詞和來源創建搜索任務（單獨搜索）
            search_tasks = []
            
            # 1. 鉅亨網 - 對每個關鍵詞單獨搜索
            for keyword in keywords:
                search_tasks.append({
                    'name': f'鉅亨網 ({keyword})',
                    'type': 'google',
                    'keywords': ['鉅亨', keyword],  # 鉅亨 + 關鍵詞
                    'language': 'zh-TW',
                    'region': 'TW',
                    'priority': 1
                })
            
            # 2. 經濟日報 - 對每個關鍵詞單獨搜索
            for keyword in keywords:
                search_tasks.append({
                    'name': f'經濟日報 ({keyword})',
                    'type': 'google',
                    'keywords': ['經濟日報', keyword],  # 經濟日報 + 關鍵詞
                    'language': 'zh-TW',
                    'region': 'TW',
                    'priority': 2
                })
            
            # 3. 對每個關鍵詞單獨搜索（Google News）
            for keyword in keywords:
                search_tasks.append({
                    'name': f'Google News ({keyword})',
                    'type': 'google',
                    'keywords': [keyword],  # 單個關鍵詞
                    'language': 'zh-TW',
                    'region': 'TW',
                    'priority': 3
                })
            
            # 4. Yahoo 財經 - 每個關鍵詞單獨搜索
            for keyword in keywords:
                search_tasks.append({
                    'name': f'Yahoo 財經 ({keyword})',
                    'type': 'google',
                    'keywords': [keyword, 'Yahoo'],
                    'language': 'zh-TW',
                    'region': 'TW',
                    'priority': 4
                })
            
            # 5. Wall Street Journal - 每個關鍵詞單獨搜索
            for keyword in keywords:
                search_tasks.append({
                    'name': f'WSJ ({keyword})',
                    'type': 'google',
                    'keywords': [keyword, 'WSJ'],
                    'language': 'zh-TW',
                    'region': 'TW',
                    'priority': 5
                })
            
            news_sources = search_tasks
        else:  # US market（與台股盤前一致：每個關鍵詞 + 每個來源分開搜，符合一個就好）
            us_sources = [
                ('Wall Street Journal', 'WSJ', 1),
                ('Yahoo Finance', 'Yahoo Finance', 2),
                ('Reuters', 'Reuters', 3),
                ('Bloomberg', 'Bloomberg', 4),
                ('CNBC', 'CNBC', 5),
                ('MarketWatch', 'MarketWatch', 6),
                ('CNN Business', 'CNN', 7),
                ('Forbes', 'Forbes', 8),
                ("Barron's", "Barron's", 9),
            ]
            search_tasks = []
            for name, source_keyword, base_priority in us_sources:
                for kw in keywords:
                    search_tasks.append({
                        'name': f'{name} ({kw})',
                        'type': 'google',
                        'keywords': [kw, source_keyword],
                        'language': 'en',
                        'region': 'US',
                        'priority': base_priority * 10 + keywords.index(kw) if kw in keywords else base_priority
                    })
            # 再加上不指定來源的單關鍵詞搜尋（等同台股的 Google News 單關鍵詞）
            for kw in keywords:
                search_tasks.append({
                    'name': f'Google News US ({kw})',
                    'type': 'google',
                    'keywords': [kw],
                    'language': 'en',
                    'region': 'US',
                    'priority': 100 + keywords.index(kw) if kw in keywords else 100
                })
            news_sources = search_tasks
        
        # 按優先級排序
        news_sources.sort(key=lambda x: x.get('priority', 99))
        
        # 從各個來源獲取新聞（每個關鍵詞單獨搜索）
        for source in news_sources:
            try:
                if source['type'] == 'google':
                    language = source.get('language', 'en')
                    region = source.get('region', 'US')
                    # 使用單個關鍵詞或關鍵詞組合搜索
                    news = self.fetch_from_google_news(source['keywords'], hours, language, region)
                elif source['type'] == 'rss':
                    # RSS源不過濾關鍵詞，因為它們本身就是相關新聞源
                    news = self.fetch_from_rss(source['url'], source.get('keywords'), hours, filter_keywords=False)
                else:
                    continue
                
                # 過濾時間範圍（確保時區一致）
                filtered_news = []
                for n in news:
                    pub_time = n.get('published_at')
                    if isinstance(pub_time, datetime):
                        # 確保有時區信息
                        if pub_time.tzinfo is None:
                            pub_time = pub_time.replace(tzinfo=timezone.utc)
                        if pub_time >= cutoff_time:
                            filtered_news.append(n)
                
                all_news.extend(filtered_news)
                time.sleep(0.3)  # 避免請求過快
                
            except Exception as e:
                print(f"Error fetching from {source.get('name', 'unknown')}: {str(e)}")
                continue
        
        # 去重（根據標題和連結），並過濾 Facebook
        seen = set()
        seen_titles = set()  # 用於檢查相似標題
        unique_news = []
        for n in all_news:
            # 過濾 Facebook 新聞
            link = n.get('link', '').lower()
            publisher = n.get('publisher', '').lower()
            title = n.get('title', '').lower().strip()
            
            if 'facebook.com' in link or 'fb.com' in link or 'facebook' in publisher or 'facebook' in title:
                continue
            
            # 檢查是否為重複新聞（根據連結和標題）
            link_key = link.strip()
            title_key = title
            
            # 如果連結相同，視為重複
            if link_key and link_key in seen:
                continue
            
            # 如果標題完全相同（去除空格和特殊字符後），視為重複
            title_normalized = ''.join(title.split()).lower()  # 移除所有空格
            if title_normalized and title_normalized in seen_titles:
                continue
            
            # 檢查標題相似度（如果標題長度>10且相似度>90%，視為重複）
            is_duplicate = False
            if len(title_normalized) > 10:
                for seen_title in seen_titles:
                    if len(seen_title) > 10:
                        # 簡單的相似度檢查：如果一個標題包含另一個標題的90%以上，視為重複
                        shorter = min(len(title_normalized), len(seen_title))
                        longer = max(len(title_normalized), len(seen_title))
                        if shorter / longer > 0.9:
                            if title_normalized in seen_title or seen_title in title_normalized:
                                is_duplicate = True
                                break
            
            if is_duplicate:
                continue
            
            # 添加到已見集合
            if link_key:
                seen.add(link_key)
            if title_normalized:
                seen_titles.add(title_normalized)
            
            unique_news.append(n)
        
        # 按標題排序（不區分大小寫，中文按Unicode順序）
        # 使用簡單的字符串排序，確保空標題排在最後
        unique_news.sort(key=lambda x: (
            x.get('title', '').lower().strip() if x.get('title') else 'zzzzzzzzzz'
        ))
        
        # 更新緩存
        self.cache[cache_key] = unique_news
        self.cache_time[cache_key] = time.time()
        
        return unique_news
    
    def extract_companies_from_text(self, text: str, company_list: Dict[str, str]) -> List[str]:
        """
        從文本中提取公司名稱
        
        Args:
            text: 文本內容
            company_list: 公司名稱字典 {symbol: name}
            
        Returns:
            出現的公司代碼列表
        """
        found_companies = []
        text_lower = text.lower()
        
        for symbol, name in company_list.items():
            # 檢查公司名稱
            if name.lower() in text_lower:
                found_companies.append(symbol)
            # 檢查股票代碼（移除 .TW 等後綴）
            symbol_base = symbol.split('.')[0]
            if symbol_base in text_lower:
                found_companies.append(symbol)
        
        return list(set(found_companies))  # 去重
    
    def get_news_volume(self, keywords: List[str], hours: int = 24) -> Dict[str, int]:
        """
        獲取新聞聲量統計（使用關鍵詞搜索）
        
        Args:
            keywords: 關鍵詞列表
            hours: 時間範圍（小時）
            
        Returns:
            公司聲量字典 {symbol: count}
        """
        result = self.get_news_volume_with_news(keywords, hours)
        return result['volume']

    def get_news_volume_with_news(
        self,
        keywords: List[str],
        hours: int = 24,
        max_news_per_company: int = 50,
        include_english: bool = True,
    ) -> Dict:
        """
        獲取新聞聲量統計，並回傳每家公司被提及的新聞列表（標題、連結等）。
        可同時搜尋中文（台股關鍵詞）與英文（美股關鍵詞）新聞並合併聲量。
        
        Args:
            keywords: 中文關鍵詞（台股）
            hours: 時間範圍（小時）
            max_news_per_company: 每家公司最多保留幾則新聞
            include_english: 是否一併搜尋英文新聞（美股關鍵詞）
        
        Returns:
            {
                'volume': { symbol: count },
                'news_by_symbol': { symbol: [ { title, link, publisher, published_at }, ... ] }
            }
        """
        company_list = {}
        company_list.update(Config.US_INDICES)
        company_list.update(Config.US_STOCKS)
        company_list.update(Config.TW_MARKETS)
        company_list.update(Config.INTERNATIONAL_MARKETS)
        
        volume_counter = Counter()
        news_by_symbol = {}
        seen_links_by_symbol = {}  # 每家公司已加入的 link，避免中英文重複
        
        def add_news_to_volume(news_list: list) -> None:
            for news in news_list:
                title = news.get('title', '')
                summary = news.get('summary', '')
                text = title + ' ' + summary
                companies = self.extract_companies_from_text(text, company_list)
                link = news.get('link', '')
                item = {
                    'title': title,
                    'link': link,
                    'publisher': news.get('publisher', ''),
                    'published_at': news.get('published_at').isoformat()
                    if isinstance(news.get('published_at'), datetime)
                    else str(news.get('published_at', '')),
                }
                for symbol in companies:
                    volume_counter[symbol] += 1
                    if symbol not in news_by_symbol:
                        news_by_symbol[symbol] = []
                        seen_links_by_symbol[symbol] = set()
                    if link and link in seen_links_by_symbol[symbol]:
                        continue
                    if len(news_by_symbol[symbol]) < max_news_per_company:
                        news_by_symbol[symbol].append(item)
                        if link:
                            seen_links_by_symbol[symbol].add(link)
        
        # 中文新聞（台股關鍵詞）
        news_list_tw = self.get_premarket_news(keywords, hours, market='taiwan')
        add_news_to_volume(news_list_tw)
        
        # 英文新聞（美股關鍵詞），與中文合併聲量
        if include_english:
            english_keywords = ['stock', 'semiconductor', 'technology', 'earnings', 'market', 'earnings report']
            try:
                news_list_us = self.get_premarket_news(english_keywords, hours, market='us')
                add_news_to_volume(news_list_us)
            except Exception as e:
                print(f"English news volume fetch skipped: {e}")
        
        return {
            'volume': dict(volume_counter),
            'news_by_symbol': news_by_symbol,
        }
