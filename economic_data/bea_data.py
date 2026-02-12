"""
從 BEA 取得 GDP、PCE 發布行事曆
來源：https://www.bea.gov/news/schedule/full 或 JSON API
"""
from datetime import datetime
from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup
import pytz
import re


def fetch_bea_schedule() -> List[Dict]:
    """
    從 BEA 官網取得 GDP、Personal Income and Outlays（PCE）發布日期。
    解析 HTML 表格取得確切日期與數據所屬月份／季度。
    """
    events = []
    us_tz = pytz.timezone('America/New_York')

    try:
        url = 'https://www.bea.gov/news/schedule/full'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return events

        soup = BeautifulSoup(response.content, 'html.parser')
        tables = soup.find_all('table')
        current_year = datetime.now().year

        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 3:
                    continue

                date_cell = cells[0].get_text(separator='\n', strip=True) if cells else ''
                release_cell = ''
                for c in cells[1:]:
                    t = c.get_text(separator='\n', strip=True)
                    if 'gdp' in t.lower() or 'personal income' in t.lower():
                        release_cell = t
                        break
                if not release_cell or not date_cell:
                    continue

                release_lower = release_cell.lower()

                # 只處理 GDP 和 Personal Income and Outlays (PCE)
                is_gdp = 'gdp' in release_lower and ('advance' in release_lower or 'second' in release_lower or 'third' in release_lower)
                is_pce = 'personal income and outlays' in release_lower

                if not is_gdp and not is_pce:
                    continue

                # 解析日期（格式：February 20 或 February 20\n8:30 AM）
                lines = date_cell.split('\n')
                date_str = lines[0].strip() if lines else ''
                time_str = lines[1].strip() if len(lines) > 1 else '8:30 AM'
                if not time_str and ':' in date_str:
                    time_str = re.search(r'\d+:\d+\s*(?:AM|PM)?', date_str, re.I)
                    time_str = time_str.group() if time_str else '8:30 AM'

                # 跳過 "To Be Announced"
                if 'to be announced' in date_str.lower():
                    continue

                # 解析 "February 20" 或 "January 8"
                date_match = re.match(r'(\w+)\s+(\d{1,2})(?:\s|$)', date_str)
                if not date_match:
                    continue

                month_str, day_str = date_match.groups()
                month_map = {
                    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
                    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
                }
                month = month_map.get(month_str.lower())
                if not month:
                    continue

                day = int(day_str)
                year = current_year
                if month < datetime.now().month:
                    year = current_year + 1
                elif month == datetime.now().month and day < datetime.now().day:
                    year = current_year + 1

                # 從表格標題或上下文取得年份（本表為 2026）
                year_el = table.find_previous(['th', 'h2', 'caption'])
                if year_el:
                    y_match = re.search(r'20\d{2}', year_el.get_text())
                    if y_match:
                        year = int(y_match.group())

                try:
                    dt = datetime(year, month, day)
                except ValueError:
                    continue

                # 解析時間
                hour, minute = 8, 30
                time_match = re.search(r'(\d+):(\d+)\s*(AM|PM)?', time_str, re.I)
                if time_match:
                    h, m, ampm = time_match.groups()
                    hour, minute = int(h), int(m)
                    if ampm and ampm.upper() == 'PM' and hour != 12:
                        hour += 12
                    elif ampm and ampm.upper() == 'AM' and hour == 12:
                        hour = 0

                release_dt = us_tz.localize(dt.replace(hour=hour, minute=minute, second=0, microsecond=0))

                if is_gdp:
                    # 解析季度：例如 "4th Quarter and Year 2025" 或 "1st Quarter 2026"
                    q_match = re.search(r'(\d)(?:st|nd|rd|th)\s+quarter[^0-9]*(\d{4})', release_lower, re.I)
                    if q_match:
                        q = int(q_match.group(1))
                        y = int(q_match.group(2))
                        event = {
                            'indicator': 'GDP',
                            'name': 'GDP',
                            'name_en': _gdp_release_name(release_cell),
                            'source': 'BEA',
                            'release_date': release_dt.isoformat(),
                            'release_date_local': release_dt.strftime('%Y-%m-%d %H:%M ET'),
                            'release_date_tw': release_dt.astimezone(pytz.timezone('Asia/Taipei')).strftime('%Y-%m-%d %H:%M CST'),
                            'frequency': 'quarterly',
                            'importance': 'high',
                            'from_bea': True,
                            'reported_year': y,
                            'reported_quarter': q,
                            'is_quarterly': True,
                        }
                        events.append(event)

                elif is_pce:
                    # 解析月份：例如 "December 2025" 或 "January 2026"
                    months_en = 'january|february|march|april|may|june|july|august|september|october|november|december'
                    m_match = re.search(rf'({months_en})\s+(\d{{4}})', release_lower)
                    if m_match:
                        m_str, y_str = m_match.groups()
                        m = month_map.get(m_str)
                        y = int(y_str)
                        if m:
                            event = {
                                'indicator': 'PCE',
                                'name': '個人消費支出 (PCE)',
                                'name_en': 'Personal Consumption Expenditures',
                                'source': 'BEA',
                                'release_date': release_dt.isoformat(),
                                'release_date_local': release_dt.strftime('%Y-%m-%d %H:%M ET'),
                                'release_date_tw': release_dt.astimezone(pytz.timezone('Asia/Taipei')).strftime('%Y-%m-%d %H:%M CST'),
                                'frequency': 'monthly',
                                'importance': 'high',
                                'from_bea': True,
                                'reported_year': y,
                                'reported_month': m,
                                'is_quarterly': False,
                            }
                            events.append(event)

    except Exception as e:
        print(f"BEA 爬取錯誤: {e}")

    return events


def _gdp_release_name(release_text: str) -> str:
    """從 BEA 發布標題提取簡短名稱。"""
    t = release_text.lower()
    if 'advance' in t:
        return 'GDP (Advance Estimate)'
    if 'second' in t:
        return 'GDP (Second Estimate)'
    if 'third' in t:
        return 'GDP (Third Estimate)'
    return 'GDP'


def fetch_bea_from_json() -> List[Dict]:
    """
    備用：從 BEA JSON API 取得 GDP、PCE 發布日期。
    無法取得所屬月份／季度，需依發布日期推估。
    """
    events = []
    us_tz = pytz.timezone('America/New_York')

    try:
        r = requests.get('https://apps.bea.gov/API/signup/release_dates.json', timeout=15)
        if not r.ok:
            return events

        data = r.json()
        gdp_dates = data.get('Gross Domestic Product', {}).get('release_dates', [])
        pce_dates = data.get('Personal Income and Outlays', {}).get('release_dates', [])

        now = datetime.now(us_tz)

        for iso_str in gdp_dates[:12]:
            try:
                dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00')).astimezone(us_tz)
                if dt < now - __import__('datetime').timedelta(days=7):
                    continue
                # 依發布月份推估季度：1月→Q4前年, 4月→Q1, 7月→Q2, 10月→Q3
                m = dt.month
                if m in (1, 2):
                    y, q = dt.year - 1, 4
                elif m in (3, 4, 5):
                    y, q = dt.year, 1
                elif m in (6, 7, 8):
                    y, q = dt.year, 2
                else:
                    y, q = dt.year, 3
                events.append({
                    'indicator': 'GDP',
                    'name': 'GDP',
                    'name_en': 'GDP',
                    'source': 'BEA',
                    'release_date': dt.isoformat(),
                    'release_date_local': dt.strftime('%Y-%m-%d %H:%M ET'),
                    'release_date_tw': dt.astimezone(pytz.timezone('Asia/Taipei')).strftime('%Y-%m-%d %H:%M CST'),
                    'frequency': 'quarterly',
                    'importance': 'high',
                    'from_bea': True,
                    'reported_year': y,
                    'reported_quarter': q,
                    'is_quarterly': True,
                })
            except Exception:
                pass

        for iso_str in pce_dates[:12]:
            try:
                dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00')).astimezone(us_tz)
                if dt < now - __import__('datetime').timedelta(days=7):
                    continue
                # PCE：月底發布，報告上月
                if dt.month == 1:
                    ry, rm = dt.year - 1, 12
                else:
                    ry, rm = dt.year, dt.month - 1
                events.append({
                    'indicator': 'PCE',
                    'name': '個人消費支出 (PCE)',
                    'name_en': 'Personal Consumption Expenditures',
                    'source': 'BEA',
                    'release_date': dt.isoformat(),
                    'release_date_local': dt.strftime('%Y-%m-%d %H:%M ET'),
                    'release_date_tw': dt.astimezone(pytz.timezone('Asia/Taipei')).strftime('%Y-%m-%d %H:%M CST'),
                    'frequency': 'monthly',
                    'importance': 'high',
                    'from_bea': True,
                    'reported_year': ry,
                    'reported_month': rm,
                    'is_quarterly': False,
                })
            except Exception:
                pass

    except Exception as e:
        print(f"BEA JSON 取得錯誤: {e}")

    return events
