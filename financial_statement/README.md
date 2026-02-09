# 財報模組：10-Q 季報

從 **SEC EDGAR** 抓取美股公司的 **10-Q 季報**（Quarterly Report）。  
資料來源為 SEC 官方 [data.sec.gov](https://data.sec.gov/)（免費、不需 API Key）。

## 使用前設定

SEC 要求請求時帶上 **User-Agent**（含聯絡方式）。請任選一種方式設定：

1. **預設**：已使用 `Trading system (trading.system.contact@gmail.com)`，無需設定即可使用。
2. **自訂**：可設環境變數 `SEC_USER_AGENT` 或在程式傳入  
   `SEC10QFetcher(user_agent="YourApp (your@email.com)")`

## 使用方式

### 列出某公司的 10-Q（由新到舊）

```python
from financial_statement import SEC10QFetcher

fetcher = SEC10QFetcher()
# 用股票代碼
reports = fetcher.list_10q(ticker="AAPL", limit=5)
for r in reports:
    print(r["filing_date"], r["report_url"])
```

### 取得最近一筆 10-Q 的網址

```python
url = fetcher.get_latest_10q_url(ticker="NVDA")
print(url)  # 可直接在瀏覽器打開
```

### 下載最近一筆 10-Q 到本地

```python
from pathlib import Path

path = fetcher.fetch_and_save_latest_10q("AAPL", save_dir=Path("C:/trading_system/financial_statement/downloads"))
if path:
    print("已存到:", path)
```

### 指令列範例

在專案目錄執行：

```powershell
cd C:\trading_system
python -c "
from financial_statement import SEC10QFetcher
f = SEC10QFetcher()
for r in f.list_10q('AAPL', limit=3):
    print(r['filing_date'], r['report_url'])
"
```

## 一次下載七巨頭 2000~2025 年 10-Q

美股七巨頭（AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA）的 10-Q 季報，依公司名稱存到 `10-q` 資料夾：

```powershell
cd C:\trading_system
python -m financial_statement.fetch_magnificent7_10q
```

- 存檔路徑：`C:\trading_system\financial_statement\10-q\`
- 每個公司一個資料夾，資料夾名稱為 SEC 回傳的公司名（例如 Apple Inc.、Microsoft Corp.）。
- 檔名格式：`{TICKER}_{申報日}.htm`，例如 `AAPL_2024-06-29.htm`。
- 已存在檔案會自動略過；重新執行可補抓缺漏。

## 下載目錄

預設下載路徑為：`financial_statement/downloads/`（若未指定 `save_dir`）。七巨頭批次下載為 `financial_statement/10-q/`。

## 匯出七巨頭財報數據到 Excel（2000~2025）

使用 SEC **Company Facts**（XBRL）結構化數據，將每季財報內的項目（營收、淨利、EPS、總資產、負債、現金等）匯出成一個 Excel 檔，每個公司一個工作表：

```powershell
cd C:\trading_system
python -m financial_statement.export_magnificent7_to_excel
```

- **存檔路徑**：`C:\trading_system\financial_statement\Data\Magnificent7_10Q_2000_2025.xlsx`
- **工作表**：總覽_欄位說明、Apple Inc.、Microsoft Corp.、…（七家公司各一表）
- **欄位**：period_end（期間結束日）、form（10-Q/10-K）、fp（Q1/Q2/Q3/FY）、fy（財年），以及 Revenue、NetIncome、EPS_Basic、TotalAssets、TotalLiabilities 等（依 SEC 有揭露的項目）
- **自動計算比率**：負債比率（TotalLiabilities/TotalAssets）、毛利率_%、淨利率_%、營業利益率_%、ROE_%、營業費用率_%、研發費用率_%、銷管費用率_%（有對應原始欄位時才會出現）
- 需安裝：`pip install openpyxl`（專案 requirements.txt 已含）

## 注意事項

- SEC 建議每秒不超過 10 次請求，程式在連續請求間已加短暫延遲。
- 僅適用 **美股**（在 SEC 申報的公司）；台股 10-Q 需另尋資料源。
