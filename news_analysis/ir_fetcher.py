"""
法人說明會數據獲取模組
從本地CSV文件讀取法說會資料（用戶需手動下載）
"""
import csv
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import time
import pytz
from pathlib import Path

class IRFetcher:
    """法人說明會數據獲取器（從本地CSV文件）"""
    
    def __init__(self, csv_dir: str = None):
        """
        初始化
        
        Args:
            csv_dir: CSV文件目錄路徑，默認為項目根目錄下的 'ir_csv' 文件夾
        """
        self.cache = {}
        self.cache_time = {}
        self.cache_duration = 3600  # 緩存1小時
        self.taiwan_tz = pytz.timezone('Asia/Taipei')
        
        # 設置CSV文件目錄
        if csv_dir:
            self.csv_dir = Path(csv_dir)
        else:
            # 默認使用項目根目錄下的 ir_csv 文件夾
            project_root = Path(__file__).parent.parent
            self.csv_dir = project_root / 'ir_csv'
        
        # 確保目錄存在
        self.csv_dir.mkdir(exist_ok=True)
        
    def _is_cache_valid(self, key: str) -> bool:
        """檢查緩存是否有效"""
        if key not in self.cache_time:
            return False
        elapsed = time.time() - self.cache_time[key]
        return elapsed < self.cache_duration
    
    def _parse_ir_date(self, date_str: str, roc_year: int) -> Optional[datetime]:
        """解析法說會日期（可能是民國年格式）"""
        if not date_str or date_str.strip() == '':
            return None
        
        date_str = date_str.strip()
        
        # 處理日期範圍（例如: 115/01/13 至 115/01/20）
        if '至' in date_str or '~' in date_str or ' ' in date_str:
            # 取第一個日期
            date_str = date_str.split('至')[0].split('~')[0].split(' ')[0].strip()
        
        # 處理民國年格式 (例如: 115/01/28)
        if '/' in date_str and len(date_str.split('/')) == 3:
            parts = date_str.split('/')
            try:
                year_part = int(parts[0])
                month_part = int(parts[1])
                day_part = int(parts[2])
                
                # 判斷是否為民國年
                # 民國年通常在 100-200 之間（對應 2011-2111 年）
                # 如果年份在 100-200 之間，視為民國年
                if 100 <= year_part <= 200:
                    # 民國年轉西元年：民國年 + 1911 = 西元年
                    year = year_part + 1911
                elif year_part < 100:
                    # 小於100也可能是民國年（例如：99年 = 2010年）
                    year = year_part + 1911
                else:
                    # 大於200，視為西元年
                    year = year_part
                
                dt = datetime(year, month_part, day_part)
                return self.taiwan_tz.localize(dt)
            except:
                pass
        
        return None
    
    def _find_csv_file(self, year: int, month: int, market: str = 'sii') -> Optional[Path]:
        """
        查找對應的CSV文件
        
        Args:
            year: 民國年（例如115表示2026年）
            month: 月份
            market: 市場別（'sii'=上市, 'otc'=上櫃）
            
        Returns:
            CSV文件路徑，如果不存在則返回None
        """
        # 轉換為西元年
        gregorian_year = year + 1911
        
        # 優先查找按月份命名的文件（例如：1月.csv, 2月.csv）
        month_names = {
            1: '1月', 2: '2月', 3: '3月', 4: '4月', 5: '5月', 6: '6月',
            7: '7月', 8: '8月', 9: '9月', 10: '10月', 11: '11月', 12: '12月'
        }
        
        month_name = month_names.get(month, f'{month}月')
        named_file = self.csv_dir / f'{month_name}.csv'
        if named_file.exists():
            return named_file
        
        # 如果沒有按月份命名的文件，查找所有CSV文件
        csv_files = list(self.csv_dir.glob('*.csv'))
        
        if not csv_files:
            return None
        
        # 按修改時間排序（最新的在前）
        csv_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        
        # 如果只有少數文件，按順序對應月份
        if len(csv_files) <= 12:
            # 假設文件按月份順序排列
            if month <= len(csv_files):
                return csv_files[month - 1]
        
        # 如果文件較多，嘗試通過文件內容判斷
        for csv_file in csv_files:
            try:
                # 嘗試讀取文件內容，檢查是否包含對應年月的數據
                with open(csv_file, 'r', encoding='big5', errors='ignore') as f:
                    reader = csv.reader(f)
                    # 讀取前20行檢查
                    found_match = False
                    for i, row in enumerate(reader):
                        if i > 20:  # 只檢查前20行
                            break
                        if len(row) >= 3:
                            # 檢查日期欄位（第3列，索引2）
                            date_str = row[2] if len(row) > 2 else ''
                            if date_str:
                                parsed_date = self._parse_ir_date(date_str, year)
                                if parsed_date:
                                    if parsed_date.year == gregorian_year and parsed_date.month == month:
                                        found_match = True
                                        break
                    if found_match:
                        return csv_file
            except:
                continue
        
        # 如果找不到匹配的，返回第一個文件
        return csv_files[0] if csv_files else None
    
    def fetch_ir_meetings(self, year: int, month: int, market: str = 'sii') -> List[Dict]:
        """
        從本地CSV文件讀取法說會資料
        
        Args:
            year: 年度（民國年，例如115表示2026年）
            month: 月份
            market: 市場別 ('sii'=上市, 'otc'=上櫃, 'rotc'=興櫃, 'pub'=公開發行)
            
        Returns:
            法說會列表
        """
        cache_key = f"ir_{year}_{month}_{market}"
        
        # 檢查緩存
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]
        
        meetings = []
        
        # 查找CSV文件
        csv_file = self._find_csv_file(year, month, market)
        
        if not csv_file or not csv_file.exists():
            print(f"未找到 {year}年{month}月 的CSV文件，請確保文件已放置在 {self.csv_dir} 目錄中")
            return []
        
        try:
            # 讀取CSV文件（使用Big5編碼）
            with open(csv_file, 'r', encoding='big5', errors='ignore') as f:
                csv_reader = csv.reader(f)
                rows = list(csv_reader)
                
                # 找到表頭行
                header_row = -1
                for i, row in enumerate(rows):
                    if len(row) > 0:
                        row_text = ' '.join(row)
                        # 檢查是否包含表頭關鍵字
                        if '公司代號' in row_text or '公司名稱' in row_text or '召開' in row_text:
                            header_row = i
                            break
                
                # 如果找到表頭，從下一行開始解析
                start_row = header_row + 1 if header_row >= 0 else 1
                
                # 解析數據行
                for row in rows[start_row:]:
                    if len(row) >= 3:  # 至少要有公司代號、名稱、日期
                        try:
                            company_code = row[0].strip() if len(row) > 0 else ''
                            company_name = row[1].strip() if len(row) > 1 else ''
                            meeting_date_str = row[2].strip() if len(row) > 2 else ''
                            meeting_time = row[3].strip() if len(row) > 3 else ''
                            location = row[4].strip() if len(row) > 4 else ''
                            
                            # 跳過空行或無效數據
                            if not company_code or not company_name:
                                continue
                            if '公司代號' in company_code or '公司名稱' in company_code:
                                continue
                            
                            # 解析日期（格式可能是 115/01/28 或 116/01/28）
                            meeting_date = self._parse_ir_date(meeting_date_str, year)
                            
                            # 如果日期解析成功，添加數據（不嚴格限制月份，因為CSV文件可能包含多個月的數據）
                            if meeting_date:
                                gregorian_year = year + 1911
                                # 允許年份有1年的誤差（因為CSV可能是去年的數據）
                                year_diff = abs(meeting_date.year - gregorian_year)
                                # 如果年份匹配，且月份也匹配，則添加
                                # 但如果查詢的月份文件不存在，也允許添加相近月份的數據（±1個月）
                                if year_diff <= 1:
                                    # 嚴格匹配月份，或者允許±1個月的誤差（處理文件命名和實際內容不匹配的情況）
                                    month_diff = abs(meeting_date.month - month)
                                    if month_diff == 0 or (month_diff <= 1 and len(meetings) == 0):
                                        meetings.append({
                                            'company_code': company_code,
                                            'company_name': company_name,
                                            'meeting_date': meeting_date.isoformat(),
                                            'meeting_time': meeting_time,
                                            'location': location,
                                            'year': year,
                                            'month': month,
                                            'market': market
                                        })
                        except Exception as e:
                            continue
                            
        except Exception as e:
            print(f"讀取CSV文件時發生錯誤: {str(e)}")
        
        # 更新緩存
        self.cache[cache_key] = meetings
        self.cache_time[cache_key] = time.time()
        
        return meetings
    
    def get_upcoming_ir_meetings(self, months_ahead: int = 3) -> List[Dict]:
        """
        獲取未來幾個月的法說會資料（使用民國年）
        
        Args:
            months_ahead: 往前查詢幾個月（預設3個月）
            
        Returns:
            法說會列表（按日期排序）
        """
        now = datetime.now(self.taiwan_tz)
        current_year = now.year
        current_month = now.month
        
        # 轉換為民國年
        roc_year = current_year - 1911
        
        all_meetings = []
        
        # 查詢當前月份及未來幾個月
        for i in range(months_ahead):
            year = current_year
            month = current_month + i
            roc_year_query = roc_year
            
            # 處理跨年
            while month > 12:
                month -= 12
                year += 1
                roc_year_query += 1
            
            # 查詢上市市場（sii）
            meetings = self.fetch_ir_meetings(roc_year_query, month, 'sii')
            all_meetings.extend(meetings)
            
            # 也可以查詢上櫃市場（otc）
            meetings_otc = self.fetch_ir_meetings(roc_year_query, month, 'otc')
            all_meetings.extend(meetings_otc)
        
        # 按日期排序
        all_meetings.sort(key=lambda x: x.get('meeting_date', ''))
        
        return all_meetings
    
    def get_ir_timeline(self, months_ahead: int = 3) -> Dict:
        """
        獲取法說會時間線資料
        
        Args:
            months_ahead: 往前查詢幾個月
            
        Returns:
            時間線資料（按日期分組）
        """
        meetings = self.get_upcoming_ir_meetings(months_ahead)
        
        # 按日期分組
        timeline = {}
        for meeting in meetings:
            date_str = meeting.get('meeting_date', '')[:10]  # 只取日期部分
            if date_str not in timeline:
                timeline[date_str] = []
            timeline[date_str].append(meeting)
        
        # 轉換為列表格式（按日期排序）
        timeline_list = []
        for date_str in sorted(timeline.keys()):
            timeline_list.append({
                'date': date_str,
                'meetings': timeline[date_str],
                'count': len(timeline[date_str])
            })
        
        return {
            'timeline': timeline_list,
            'total_meetings': len(meetings),
            'date_range': {
                'start': timeline_list[0]['date'] if timeline_list else None,
                'end': timeline_list[-1]['date'] if timeline_list else None
            },
            'timestamp': datetime.now(self.taiwan_tz).isoformat()
        }
