"""
经济日历数据获取模块
获取重要经济数据发布时间（CPI, PPI, PCE, 非农就业等）
"""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup
import pytz

class EconomicCalendar:
    """经济日历数据获取器"""
    
    def __init__(self):
        self.us_tz = pytz.timezone('America/New_York')
        self.cache = {}
        self.cache_time = {}
        self.cache_duration = 3600  # 缓存1小时
        self._cpi_ctx_cache = None
        self._cpi_ctx_cache_time = None

        # 重要經濟指標定義（繁體中文，僅用於 BLS 爬取後顯示）
        self.indicators = {
            'CPI': {
                'name': '消費者物價指數 (CPI)',
                'name_en': 'Consumer Price Index',
                'source': 'BLS',
                'frequency': 'monthly',
                'typical_day': 'mid_month',
                'typical_time': '08:30 ET'
            },
            'PPI': {
                'name': '生產者物價指數 (PPI)',
                'name_en': 'Producer Price Index',
                'source': 'BLS',
                'frequency': 'monthly',
                'typical_day': 'mid_month',
                'typical_time': '08:30 ET'
            },
            'PCE': {
                'name': '個人消費支出 (PCE)',
                'name_en': 'Personal Consumption Expenditures',
                'source': 'BEA',
                'frequency': 'monthly',
                'typical_day': 'end_month',
                'typical_time': '08:30 ET'
            },
            'NFP': {
                'name': '非農就業人數',
                'name_en': 'Non-Farm Payrolls',
                'source': 'BLS',
                'frequency': 'monthly',
                'typical_day': 'first_friday',
                'typical_time': '08:30 ET'
            },
            'FOMC': {
                'name': 'FOMC 利率決議',
                'name_en': 'FOMC Rate Decision',
                'source': 'Fed',
                'frequency': '8_times_per_year',
                'typical_day': 'varies',
                'typical_time': '14:00 ET'
            },
            'GDP': {
                'name': 'GDP 初值',
                'name_en': 'GDP Preliminary',
                'source': 'BEA',
                'frequency': 'quarterly',
                'typical_day': 'end_quarter',
                'typical_time': '08:30 ET'
            },
            'UNEMPLOYMENT': {
                'name': '失業率',
                'name_en': 'Unemployment Rate',
                'source': 'BLS',
                'frequency': 'monthly',
                'typical_day': 'first_friday',
                'typical_time': '08:30 ET'
            },
            'RETAIL_SALES': {
                'name': '零售銷售',
                'name_en': 'Retail Sales',
                'source': 'Census',
                'frequency': 'monthly',
                'typical_day': 'mid_month',
                'typical_time': '08:30 ET'
            },
            'ISM_MANUFACTURING': {
                'name': 'ISM 製造業 PMI',
                'name_en': 'ISM Manufacturing PMI',
                'source': 'ISM',
                'frequency': 'monthly',
                'typical_day': 'first_business_day',
                'typical_time': '10:00 ET'
            },
            'ISM_SERVICES': {
                'name': 'ISM 服務業 PMI',
                'name_en': 'ISM Services PMI',
                'source': 'ISM',
                'frequency': 'monthly',
                'typical_day': 'first_business_day',
                'typical_time': '10:00 ET'
            }
        }
    
    def _get_first_friday(self, year: int, month: int) -> datetime:
        """获取指定年月的第一个周五"""
        first_day = datetime(year, month, 1)
        # 找到第一个周五
        days_ahead = (4 - first_day.weekday()) % 7  # 周五是4
        if days_ahead == 0 and first_day.weekday() != 4:
            days_ahead = 7
        first_friday = first_day + timedelta(days=days_ahead)
        return first_friday
    
    def _get_mid_month(self, year: int, month: int) -> datetime:
        """获取月中日期（约15号）"""
        return datetime(year, month, 15)
    
    def _get_end_month(self, year: int, month: int) -> datetime:
        """获取月末日期"""
        if month == 12:
            return datetime(year, month, 31)
        else:
            next_month = datetime(year, month + 1, 1)
            return next_month - timedelta(days=1)
    
    def _calculate_release_date(self, indicator_key: str, year: int, month: int) -> Optional[datetime]:
        """根据指标类型计算预计发布日期"""
        indicator = self.indicators.get(indicator_key)
        if not indicator:
            return None
        
        typical_day = indicator.get('typical_day')
        typical_time = indicator.get('typical_time', '08:30 ET')
        
        # 解析时间
        time_str = typical_time.split()[0]  # 例如 "08:30"
        hour, minute = map(int, time_str.split(':'))
        
        if typical_day == 'first_friday':
            date = self._get_first_friday(year, month)
        elif typical_day == 'mid_month':
            date = self._get_mid_month(year, month)
        elif typical_day == 'end_month':
            date = self._get_end_month(year, month)
        elif typical_day == 'first_business_day':
            # 每月第一个工作日（通常是1号，如果是周末则顺延）
            date = datetime(year, month, 1)
            while date.weekday() >= 5:  # 周六或周日
                date += timedelta(days=1)
        else:
            return None
        
        # 设置时间
        date = date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        # 转换为美东时间
        date = self.us_tz.localize(date)
        
        return date
    
    def get_upcoming_events(self, months_ahead: int = 3) -> List[Dict]:
        """
        获取未来几个月的重要经济事件
        
        Args:
            months_ahead: 向前看几个月（默认3个月）
        
        Returns:
            事件列表，按时间排序
        """
        now = datetime.now(self.us_tz)
        events = []
        
        # 生成未来几个月的事件
        for month_offset in range(months_ahead):
            target_date = now + timedelta(days=30 * month_offset)
            year = target_date.year
            month = target_date.month
            
            # 为每个指标生成预计发布日期
            for indicator_key, indicator_info in self.indicators.items():
                release_date = self._calculate_release_date(indicator_key, year, month)
                
                if release_date and release_date >= now:
                    events.append({
                        'indicator': indicator_key,
                        'name': indicator_info['name'],
                        'name_en': indicator_info['name_en'],
                        'source': indicator_info['source'],
                        'release_date': release_date.isoformat(),
                        'release_date_local': release_date.strftime('%Y-%m-%d %H:%M ET'),
                        'release_date_tw': release_date.astimezone(pytz.timezone('Asia/Taipei')).strftime('%Y-%m-%d %H:%M CST'),
                        'frequency': indicator_info['frequency'],
                        'importance': self._get_importance(indicator_key)
                    })
        
        # 按时间排序
        events.sort(key=lambda x: x['release_date'])
        
        # 移除重复（同一指标在同一个月可能重复）
        seen = set()
        unique_events = []
        for event in events:
            key = (event['indicator'], event['release_date'][:10])  # 按指标和日期去重
            if key not in seen:
                seen.add(key)
                unique_events.append(event)
        
        return unique_events
    
    def _get_importance(self, indicator_key: str) -> str:
        """获取指标重要性"""
        high_importance = ['CPI', 'PPI', 'PCE', 'NFP', 'FOMC', 'GDP', 'UNEMPLOYMENT']
        if indicator_key in high_importance:
            return 'high'
        return 'medium'
    
    def _parse_bls_date(self, date_str: str, year: int, month: int) -> Optional[datetime]:
        """解析BLS日期字符串，例如 '2' 表示该月的第2天"""
        try:
            day = int(date_str.strip())
            date = datetime(year, month, day)
            return self.us_tz.localize(date)
        except:
            return None
    
    def _parse_bls_time(self, time_str: str) -> tuple:
        """解析BLS时间字符串，例如 '08:30 AM' 返回 (8, 30)"""
        try:
            time_str = time_str.strip().upper()
            if 'AM' in time_str:
                time_part = time_str.replace('AM', '').strip()
                hour, minute = map(int, time_part.split(':'))
                if hour == 12:
                    hour = 0
            elif 'PM' in time_str:
                time_part = time_str.replace('PM', '').strip()
                hour, minute = map(int, time_part.split(':'))
                if hour != 12:
                    hour += 12
            else:
                # 默认8:30 AM
                hour, minute = 8, 30
            return hour, minute
        except:
            return 8, 30  # 默认时间
    
    def _map_bls_indicator(self, bls_name: str) -> Optional[str]:
        """将BLS指标名称映射到我们的指标key"""
        bls_name_lower = bls_name.lower()
        
        if 'consumer price index' in bls_name_lower or 'cpi' in bls_name_lower:
            return 'CPI'
        elif 'producer price index' in bls_name_lower or 'ppi' in bls_name_lower:
            return 'PPI'
        elif 'employment situation' in bls_name_lower:
            return 'NFP'  # 非农就业
        elif 'unemployment' in bls_name_lower and 'rate' in bls_name_lower:
            return 'UNEMPLOYMENT'
        elif 'retail sales' in bls_name_lower:
            return 'RETAIL_SALES'
        
        return None
    
    def fetch_from_bls_schedule(self, months_ahead: int = 1) -> List[Dict]:
        """
        从BLS官网获取实际发布时间表
        只爬取近一个月的数据
        
        Args:
            months_ahead: 向前爬取几个月（默认1个月）
        
        Returns:
            事件列表
        """
        events = []
        now = datetime.now(self.us_tz)
        
        try:
            # 爬取当前月和下个月的数据
            for month_offset in range(months_ahead):
                target_date = now + timedelta(days=30 * month_offset)
                year = target_date.year
                month = target_date.month
                
                # BLS URL格式: https://www.bls.gov/schedule/2026/02_sched.htm
                url = f'https://www.bls.gov/schedule/{year}/{month:02d}_sched.htm'
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }
                
                response = requests.get(url, headers=headers, timeout=15)
                if response.status_code != 200:
                    continue
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # 查找日历表格 - BLS使用table标签
                tables = soup.find_all('table')
                
                for table in tables:
                    rows = table.find_all('tr')
                    
                    for row in rows:
                        cells = row.find_all(['td', 'th'])
                        
                        # 遍历每个单元格
                        for cell in cells:
                            cell_text = cell.get_text(separator='\n', strip=True)
                            
                            if not cell_text:
                                continue
                            
                            lines = [line.strip() for line in cell_text.split('\n') if line.strip()]
                            
                            # 查找日期数字（通常是1-31）
                            day = None
                            for line in lines:
                                if line.isdigit() and 1 <= int(line) <= 31:
                                    day = int(line)
                                    break
                            
                            if not day:
                                continue
                            
                            # 解析日期
                            release_date = self._parse_bls_date(str(day), year, month)
                            if not release_date:
                                continue
                            
                            # 查找指标名称和时间
                            indicator_name = None
                            time_str = None
                            
                            for line in lines:
                                line_lower = line.lower()
                                # 跳过日期数字和月份年份
                                if line.isdigit() or '2026' in line or '2025' in line:
                                    continue
                                
                                # 查找时间（包含AM或PM）
                                if ('am' in line_lower or 'pm' in line_lower) and ':' in line:
                                    time_str = line
                                # 查找指标名称（通常是较长的文本，不包含时间）
                                elif len(line) > 10 and 'am' not in line_lower and 'pm' not in line_lower:
                                    if not indicator_name or len(line) > len(indicator_name):
                                        indicator_name = line
                            
                            if not indicator_name:
                                continue
                            
                            if not time_str:
                                # 如果没有找到时间，使用默认时间
                                time_str = '08:30 AM'
                            
                            # 映射指标
                            indicator_key = self._map_bls_indicator(indicator_name)
                            if not indicator_key:
                                continue
                            
                            # 解析时间
                            hour, minute = self._parse_bls_time(time_str)
                            
                            # 设置具体时间
                            release_date = release_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                            
                            # 获取指标信息
                            indicator_info = self.indicators.get(indicator_key)
                            if not indicator_info:
                                continue
                            
                            # 创建事件
                            event = {
                                'indicator': indicator_key,
                                'name': indicator_info['name'],
                                'name_en': indicator_info['name_en'],
                                'source': indicator_info['source'],
                                'release_date': release_date.isoformat(),
                                'release_date_local': release_date.strftime('%Y-%m-%d %H:%M ET'),
                                'release_date_tw': release_date.astimezone(pytz.timezone('Asia/Taipei')).strftime('%Y-%m-%d %H:%M CST'),
                                'frequency': indicator_info['frequency'],
                                'importance': self._get_importance(indicator_key),
                                'from_bls': True  # 标记这是从BLS爬取的
                            }
                            
                            events.append(event)
                
        except Exception as e:
            print(f"从BLS获取数据时出错: {e}")
        
        return events

    def _get_cpi_context_cached(self, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """取得 CPI 前月、前年、預測（含緩存）"""
        if not force_refresh and self._cpi_ctx_cache is not None and self._cpi_ctx_cache_time:
            age = (datetime.now() - self._cpi_ctx_cache_time).total_seconds()
            if age < self.cache_duration:
                return self._cpi_ctx_cache
        try:
            from economic_data.cpi_data import get_cpi_context
            self._cpi_ctx_cache = get_cpi_context()
            self._cpi_ctx_cache_time = datetime.now()
            return self._cpi_ctx_cache
        except Exception as e:
            print(f"取得 CPI 數據時出錯: {e}")
            return self._cpi_ctx_cache  # 沿用舊快取或 None
    
    def get_economic_calendar(self, force_refresh: bool = False) -> Dict:
        """
        获取经济日历数据
        优先使用从BLS爬取的实际日期，如果没有则使用估算日期
        
        Args:
            force_refresh: 是否强制刷新缓存（只有用户按更新按钮时才为True）
        
        Returns:
            包含事件列表和时间戳的字典
        """
        cache_key = 'economic_calendar'
        
        # 只有用户主动刷新时才从BLS爬取，否则使用缓存
        if force_refresh:
            # 清除缓存，强制重新获取
            if cache_key in self.cache:
                del self.cache[cache_key]
            if cache_key in self.cache_time:
                del self.cache_time[cache_key]
        
        # 检查缓存
        if not force_refresh and cache_key in self.cache:
            cache_age = (datetime.now() - self.cache_time.get(cache_key, datetime.min)).total_seconds()
            if cache_age < self.cache_duration:
                return self.cache[cache_key]
        
        # 僅使用 BLS 爬取之確切日期，不顯示估算日期
        # 抓「當月 + 下月」兩個月的行事曆
        bls_events = self.fetch_from_bls_schedule(months_ahead=2)
        
        if bls_events:
            events = bls_events
        else:
            # 無確切日期時不顯示估算，由使用者每月自行至 BLS 查看後更新
            events = []
        
        # 按时间排序
        events.sort(key=lambda x: x['release_date'])
        
        # 去重（同一指标在同一天只保留一个）
        seen = set()
        unique_events = []
        for event in events:
            key = (event['indicator'], event['release_date'][:10])  # 按指标和日期去重
            if key not in seen:
                seen.add(key)
                unique_events.append(event)
        
        # 為 CPI（及可擴充其他指標）補充前月、前年、預測值
        cpi_ctx = self._get_cpi_context_cached(force_refresh)
        for event in unique_events:
            if event.get('indicator') == 'CPI' and cpi_ctx:
                if cpi_ctx.get('prev_month_value') is not None:
                    event['prev_month_value'] = cpi_ctx['prev_month_value']
                if cpi_ctx.get('prev_year_value') is not None:
                    event['prev_year_value'] = cpi_ctx['prev_year_value']
                if cpi_ctx.get('forecast_value') is not None:
                    event['forecast_value'] = cpi_ctx['forecast_value']
                elif cpi_ctx.get('forecast_hint'):
                    event['forecast_hint'] = cpi_ctx['forecast_hint']

        # 分离未来和过去的事件
        now = datetime.now(self.us_tz)
        upcoming = []
        past = []
        
        for event in unique_events:
            event_time = datetime.fromisoformat(event['release_date'].replace('Z', '+00:00'))
            if event_time >= now:
                upcoming.append(event)
            else:
                past.append(event)
        
        result = {
            'upcoming': upcoming,
            'past': past,
            'timestamp': datetime.now().isoformat(),
            'source': 'BLS' if bls_events else 'none'
        }
        
        # 更新缓存
        self.cache[cache_key] = result
        self.cache_time[cache_key] = datetime.now()
        
        return result
