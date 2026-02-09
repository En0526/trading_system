"""
下載美股七巨頭 2000~2025 年 10-Q 季報到 C:\\trading_system\\financial_statement\\10-q
每個公司一個資料夾，資料夾名稱使用 SEC 回傳的公司名。
執行：在專案根目錄執行  python -m financial_statement.fetch_magnificent7_10q
"""
import re
import time
from pathlib import Path

# 專案根目錄
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_BASE = Path(r"C:\trading_system\financial_statement\10-q")

# 美股七巨頭 ticker
MAGNIFICENT_7 = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]


def sanitize_folder_name(name: str) -> str:
    """將公司名轉成可當 Windows 資料夾名稱（去掉非法字元）。"""
    if not name:
        return "Unknown"
    # Windows 不允許 \ / : * ? " < > |
    s = re.sub(r'[\\/:*?"<>|]', " ", name)
    s = re.sub(r"\s+", " ", s).strip()
    return s or "Unknown"


def main():
    import sys
    sys.path.insert(0, str(PROJECT_ROOT))
    from financial_statement import SEC10QFetcher

    fetcher = SEC10QFetcher()
    OUTPUT_BASE.mkdir(parents=True, exist_ok=True)

    for ticker in MAGNIFICENT_7:
        print(f"\n[{ticker}] 取得 10-Q 列表 (2000~2025)...")
        reports = fetcher.list_10q(
            ticker=ticker,
            limit=None,
            year_start=2000,
            year_end=2025,
        )
        if not reports:
            print(f"  -> 無符合條件的 10-Q，略過")
            continue
        company_name = reports[0].get("company_name") or ticker
        folder_name = sanitize_folder_name(company_name)
        company_dir = OUTPUT_BASE / folder_name
        company_dir.mkdir(parents=True, exist_ok=True)
        print(f"  -> 公司: {company_name}，共 {len(reports)} 筆，存到: {company_dir}")

        for i, r in enumerate(reports):
            filing_date = r.get("filing_date") or ""
            ticker_sym = (r.get("ticker") or ticker).upper()
            # 檔名例: AAPL_2004-06-26.html
            primary_doc = r.get("primary_document") or ""
            ext = "htm" if primary_doc.lower().endswith(".htm") else "html"
            filename = f"{ticker_sym}_{filing_date}.{ext}"
            filepath = company_dir / filename
            if filepath.exists():
                print(f"    已有 {filename}，略過")
                continue
            url = r.get("report_url")
            if not url:
                continue
            time.sleep(0.25)
            saved = fetcher.download_10q(report_url=url, save_dir=company_dir, filename=filename)
            if saved:
                print(f"    已下載 {filename}")
            else:
                print(f"    下載失敗 {filename}")

    print("\n完成。")


if __name__ == "__main__":
    main()
