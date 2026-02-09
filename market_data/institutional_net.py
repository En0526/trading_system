"""
三大法人買賣超資料（證交所 BFI82U 三大法人買賣金額統計表）
資料來源：https://www.twse.com.tw/zh/trading/foreign/bfi82u.html

若證交所連線失敗（SSL、阻擋或無資料），可改用手動下載：
至上述網頁選擇日期後點「CSV 下載」，將檔案存到 institutional_csv 資料夾，檔名 YYYYMMDD.csv
"""
import requests
import csv
import time
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from io import StringIO

# 關閉 SSL 警告（部分環境對 twse.com.tw 憑證會報錯）
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.twse.com.tw/zh/trading/foreign/bfi82u.html',
})
BFI82U_URL = 'https://www.twse.com.tw/exchangeReport/BFI82U'

# 專案根目錄（此檔在 market_data/ 下）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTITUTIONAL_CSV_DIR = os.path.join(_PROJECT_ROOT, 'institutional_csv')

# 緩存：當日內不重複拉整段區間
_ytd_cache: Optional[Dict] = None
_ytd_cache_date: Optional[str] = None
# 最後一次連線錯誤（用於無資料時顯示可能原因）
_last_fetch_error: Optional[str] = None


def _parse_int(s: str) -> int:
    """將「1,234」或「-123」轉成整數（單位：元）。"""
    if not s or not isinstance(s, str):
        return 0
    s = s.strip().replace(',', '').replace('"', '').replace('=', '')
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return 0


def _trading_days(start: datetime, end: datetime) -> List[datetime]:
    """產生 start~end 之間的交易日（簡單以週一～五為交易日，不排除國定假日）。"""
    out = []
    d = start.date()
    end_date = end.date()
    while d <= end_date:
        if d.weekday() < 5:  # 0=Mon .. 4=Fri
            out.append(datetime.combine(d, datetime.min.time()))
        d += timedelta(days=1)
    return out


def _parse_bfi82u_csv(text: str, date_str: str) -> Optional[Dict[str, int]]:
    """解析 BFI82U CSV 內容（API 或本地檔），回傳該日外資與三大法人合計買賣超（元）。"""
    if not text or 'html' in text.lower()[:200]:
        return None
    text = text.lstrip('\ufeff')
    lines = [line for line in text.split('\n') if line.strip()]
    if len(lines) < 3:
        return None
    header_idx = None
    for i, line in enumerate(lines):
        if '類別' in line or '買賣超' in line or '證券名稱' in line:
            header_idx = i
            break
        if '買' in line and '賣' in line and ('買進' in line or '賣出' in line or '金額' in line) and ',' in line:
            row_pre = next(csv.reader(StringIO(line)))
            if len(row_pre) >= 4:
                header_idx = i
                break
    if header_idx is None:
        return None
    reader = csv.reader(StringIO('\n'.join(lines[header_idx:])))
    header = next(reader)
    col_idx = None
    for j, h in enumerate(header):
        h = (h or '').strip()
        if '買賣超' in h:
            col_idx = j
            break
        if '買' in h and '賣' in h and j >= 2:
            col_idx = j
            break
    if col_idx is None:
        return None
    foreign_net = None
    trust_net = None
    dealer_net = 0
    total_net = None
    components = []
    category_col = 0
    for row in reader:
        if len(row) <= max(category_col, col_idx):
            continue
        label = (row[category_col] or '').strip().replace(' ', '')
        value = _parse_int(row[col_idx]) if col_idx < len(row) else 0
        if ('外資' in label and ('陸資' in label or '及' in label or '與' in label)) or '外資及陸資' in label or '外資與陸資' in label:
            foreign_net = value
            components.append(value)
        elif '投信' in label and '自營' not in label:
            trust_net = value
            components.append(value)
        elif '自營' in label or '證券自營商' in label or '外資自營商' in label:
            dealer_net = (dealer_net or 0) + value
            components.append(value)
        elif '合計' in label or '總計' in label or '總和' in label or ('合' in label and '計' in label):
            total_net = value
    if total_net is None and components:
        total_net = sum(components)
    if foreign_net is None:
        foreign_net = 0
    if trust_net is None:
        trust_net = 0
    if dealer_net is None:
        dealer_net = 0
    if total_net is None:
        total_net = foreign_net + trust_net + dealer_net
    return {
        'date': date_str,
        'foreign_net': foreign_net,
        'trust_net': trust_net,
        'dealer_net': dealer_net,
        'total_net': total_net,
    }


def fetch_bfi82u_day(date: datetime) -> Optional[Dict[str, int]]:
    """
    取得單日 BFI82U 報表（證交所 API），回傳該日外資與三大法人合計買賣超（元）。
    若連線失敗或解析失敗會設定 _last_fetch_error 並回傳 None。
    """
    global _last_fetch_error
    date_str = date.strftime('%Y%m%d')
    try:
        r = SESSION.get(
            BFI82U_URL,
            params={'response': 'csv', 'date': date_str},
            timeout=15,
            verify=False
        )
        r.raise_for_status()
        text = r.text
    except Exception as e:
        _last_fetch_error = str(e)
        return None
    if not text or 'html' in text.lower()[:200]:
        _last_fetch_error = '證交所未回傳 CSV（可能為非交易日或網站阻擋）'
        return None
    parsed = _parse_bfi82u_csv(text, date_str)
    if parsed is None:
        _last_fetch_error = '證交所回傳內容無法解析（非預期 CSV 格式）'
        return None
    _last_fetch_error = None
    return parsed


def list_uploaded_dates() -> List[str]:
    """掃描 institutional_csv 資料夾，回傳已有 CSV 的日期列表（YYYYMMDD），已排序。"""
    import re
    if not os.path.isdir(INSTITUTIONAL_CSV_DIR):
        return []
    dates = []
    for name in os.listdir(INSTITUTIONAL_CSV_DIR):
        if not name.lower().endswith('.csv'):
            continue
        base = name[:-4]  # 去掉 .csv
        # 支援 YYYYMMDD 或 BFI82U_YYYYMMDD
        m = re.match(r'^(?:BFI82U_)?(\d{8})$', base)
        if m:
            dates.append(m.group(1))
    return sorted(set(dates))


def save_uploaded_csv(date_str: str, content: bytes) -> None:
    """將上傳的 CSV 存到 institutional_csv/YYYYMMDD.csv，並清除快取。"""
    global _ytd_cache, _ytd_cache_date
    os.makedirs(INSTITUTIONAL_CSV_DIR, exist_ok=True)
    path = os.path.join(INSTITUTIONAL_CSV_DIR, f'{date_str}.csv')
    with open(path, 'wb') as f:
        f.write(content)
    _ytd_cache = None
    _ytd_cache_date = None


def try_parse_date_from_filename(filename: str) -> Optional[str]:
    """從檔名嘗試解析日期，例如 BFI82U_day_20260102.csv、20260102.csv。回傳 YYYYMMDD。"""
    import re
    if not filename:
        return None
    base = os.path.splitext(filename)[0]
    m = re.search(r'(\d{8})', base)
    if m:
        s = m.group(1)
        y, mon, d = int(s[:4]), int(s[4:6]), int(s[6:8])
        if 1990 <= y <= 2030 and 1 <= mon <= 12 and 1 <= d <= 31:
            return s
    return None


def try_parse_date_from_csv(text: str) -> Optional[str]:
    """從 BFI82U CSV 內容嘗試解析日期，回傳 YYYYMMDD 或 None。"""
    import re
    # 常見：資料日期 20260102、或 115/01/02（民國）
    for line in text.split('\n')[:10]:
        line = line.strip()
        m = re.search(r'(\d{4})[/\-]?(\d{2})[/\-]?(\d{2})', line)
        if m:
            return m.group(1) + m.group(2) + m.group(3)
        m = re.search(r'(\d{3})/(\d{1,2})/(\d{1,2})', line)  # 民國 115/1/2
        if m:
            y = int(m.group(1)) + 1911
            return f'{y}{int(m.group(2)):02d}{int(m.group(3)):02d}'
    return None


def _load_bfi82u_from_file(date_str: str) -> Optional[Dict[str, int]]:
    """從 institutional_csv/ 讀取手動下載的 BFI82U CSV，檔名 YYYYMMDD.csv 或 BFI82U_YYYYMMDD.csv。證交所多為 Big5，先試 Big5 再試 UTF-8。"""
    for name in (f'{date_str}.csv', f'BFI82U_{date_str}.csv'):
        path = os.path.join(INSTITUTIONAL_CSV_DIR, name)
        if not os.path.isfile(path):
            continue
        text = None
        for encoding in ('cp950', 'big5', 'utf-8', 'utf-8-sig'):
            try:
                with open(path, 'r', encoding=encoding) as f:
                    text = f.read()
                break
            except (UnicodeDecodeError, UnicodeError):
                continue
        if not text:
            continue
        parsed = _parse_bfi82u_csv(text, date_str)
        if parsed:
            return parsed
    return None


def get_institutional_net_ytd(force_refresh: bool = False) -> Dict:
    """
    從今年 1/1 起算到今日，取得每日三大法人買賣超，並計算當年累計值。
    回傳格式供前端畫「當年累計」柱狀圖：三大法人總和、外資。
    """
    global _ytd_cache, _ytd_cache_date
    today_str = datetime.now().strftime('%Y-%m-%d')
    if not force_refresh and _ytd_cache is not None and _ytd_cache_date == today_str:
        return _ytd_cache

    now = datetime.now()
    year_start = datetime(now.year, 1, 1)
    end = now
    days = _trading_days(year_start, end)

    daily_list: List[Dict] = []
    cumulative_total = 0
    cumulative_foreign = 0
    cumulative_trust = 0
    cumulative_dealer = 0

    for i, d in enumerate(days):
        date_str = d.strftime('%Y%m%d')
        row = _load_bfi82u_from_file(date_str)
        if row is None:
            if i > 0:
                time.sleep(0.2)
            row = fetch_bfi82u_day(d)
        if row is None:
            continue
        f_net = row.get('foreign_net') or 0
        tr_net = row.get('trust_net') or 0
        dl_net = row.get('dealer_net') or 0
        t_net = row.get('total_net')
        if t_net is None:
            t_net = f_net + tr_net + dl_net
        cumulative_foreign += f_net
        cumulative_trust += tr_net
        cumulative_dealer += dl_net
        cumulative_total += t_net
        daily_list.append({
            'date': row['date'],
            'date_display': f"{row['date'][:4]}-{row['date'][4:6]}-{row['date'][6:8]}",
            'foreign_net': f_net,
            'trust_net': tr_net,
            'dealer_net': dl_net,
            'total_net': t_net,
            'cumulative_foreign': cumulative_foreign,
            'cumulative_trust': cumulative_trust,
            'cumulative_dealer': cumulative_dealer,
            'cumulative_total': cumulative_total,
        })

    labels = [x['date_display'] for x in daily_list]
    cum_total_millions = [round(x['cumulative_total'] / 1e6, 2) for x in daily_list]
    cum_foreign_millions = [round(x['cumulative_foreign'] / 1e6, 2) for x in daily_list]
    cum_trust_millions = [round(x['cumulative_trust'] / 1e6, 2) for x in daily_list]
    cum_dealer_millions = [round(x['cumulative_dealer'] / 1e6, 2) for x in daily_list]

    result = {
        'labels': labels,
        'cumulative_total_millions': cum_total_millions,
        'cumulative_foreign_millions': cum_foreign_millions,
        'cumulative_trust_millions': cum_trust_millions,
        'cumulative_dealer_millions': cum_dealer_millions,
        'daily': daily_list,
        'year': now.year,
    }
    if not daily_list:
        result['fetch_error'] = _last_fetch_error or '無法取得資料'
        result['csv_help'] = (
            '若為連線或 SSL 問題，可改用手動下載：至證交所 '
            '三大法人買賣金額統計表 選擇日期後點「CSV 下載」，'
            '將檔案存到 institutional_csv 資料夾，檔名 YYYYMMDD.csv 後按更新。'
        )
    _ytd_cache = result
    _ytd_cache_date = today_str
    return result
