"""
範例：抓取指定公司的 10-Q 季報列表，並可下載最近一筆到本地。
使用方式（在專案根目錄 C:\\trading_system 執行）：
  python -m financial_statement.fetch_10q_example AAPL
  python -m financial_statement.fetch_10q_example NVDA --download
  python -m financial_statement.fetch_10q_example MSFT --limit 5
"""
import argparse
import sys
from pathlib import Path

# 讓專案根目錄在 path 裡
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from financial_statement import SEC10QFetcher


def main():
    parser = argparse.ArgumentParser(description="列出公司 10-Q 季報，可選下載最近一筆")
    parser.add_argument("ticker", help="股票代碼，例如 AAPL, NVDA")
    parser.add_argument("--limit", type=int, default=10, help="最多列出幾筆（預設 10）")
    parser.add_argument("--download", action="store_true", help="下載最近一筆 10-Q 到 financial_statement/downloads")
    args = parser.parse_args()

    fetcher = SEC10QFetcher()
    ticker = args.ticker.upper().strip()
    reports = fetcher.list_10q(ticker=ticker, limit=args.limit)

    if not reports:
        print(f"找不到 {ticker} 的 10-Q 季報。")
        return

    print(f"{reports[0].get('company_name', ticker)} ({ticker}) 10-Q 季報（最近 {len(reports)} 筆）：\n")
    for r in reports:
        print(f"  {r['filing_date']}  {r['report_url']}")

    if args.download:
        save_dir = Path(__file__).resolve().parent / "downloads"
        path = fetcher.fetch_and_save_latest_10q(ticker, save_dir=save_dir)
        if path:
            print(f"\n已下載最近一筆 10-Q 到: {path}")
        else:
            print("\n下載失敗。")


if __name__ == "__main__":
    main()
