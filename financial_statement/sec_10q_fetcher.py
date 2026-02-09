"""
從 SEC EDGAR 抓取公司 10-Q 季報
資料來源：SEC 官方 data.sec.gov（免費、無 API Key）
"""
import os
import requests
import time
from typing import Dict, List, Optional
from pathlib import Path

# SEC 要求請求時帶上 User-Agent（可設環境變數 SEC_USER_AGENT 覆蓋）
SEC_USER_AGENT = os.environ.get("SEC_USER_AGENT") or "Trading system (trading.system.contact@gmail.com)"
SEC_BASE = "https://data.sec.gov"
SEC_ARCHIVES = "https://www.sec.gov/Archives/edgar/data"


def _headers() -> Dict[str, str]:
    return {
        "User-Agent": SEC_USER_AGENT,
        "Accept": "application/json",
        "Host": "data.sec.gov",
    }


def _archives_headers() -> Dict[str, str]:
    return {
        "User-Agent": SEC_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Host": "www.sec.gov",
    }


class SEC10QFetcher:
    """從 SEC EDGAR 取得公司 10-Q 季報列表與連結"""

    def __init__(self, user_agent: Optional[str] = None):
        self.session = requests.Session()
        self._user_agent = user_agent or SEC_USER_AGENT
        self._tickers_cache: Dict[str, Dict] = {}
        self._cik_cache: Dict[str, str] = {}

    def _get_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": self._user_agent,
            "Accept": "application/json",
            "Host": "data.sec.gov",
        }

    def _get_tickers(self) -> Dict:
        """取得 SEC 公司 ticker -> CIK 對照表（會快取）"""
        if self._tickers_cache:
            return self._tickers_cache
        url = "https://www.sec.gov/files/company_tickers.json"
        r = self.session.get(url, headers={"User-Agent": self._user_agent}, timeout=30)
        r.raise_for_status()
        self._tickers_cache = r.json()
        return self._tickers_cache

    def ticker_to_cik(self, ticker: str) -> Optional[str]:
        """由股票代碼取得 SEC CIK（10 碼，前補 0）"""
        ticker_upper = ticker.upper().strip()
        if ticker_upper in self._cik_cache:
            return self._cik_cache[ticker_upper]
        data = self._get_tickers()
        for _, v in data.items():
            t = (v.get("ticker") or "").strip().upper()
            if t == ticker_upper:
                cik = str(v.get("cik_str", ""))
                if cik:
                    cik_padded = cik.zfill(10)
                    self._cik_cache[ticker_upper] = cik_padded
                    return cik_padded
        return None

    def get_submissions(self, cik: str) -> Optional[Dict]:
        """取得公司 submissions（含近期申報列表）"""
        cik_padded = cik.zfill(10) if not cik.startswith("0") else cik
        url = f"{SEC_BASE}/submissions/CIK{cik_padded}.json"
        r = self.session.get(url, headers=self._get_headers(), timeout=30)
        if not r.ok:
            return None
        return r.json()

    def list_10q(
        self,
        ticker: Optional[str] = None,
        cik: Optional[str] = None,
        limit: Optional[int] = 20,
        year_start: Optional[int] = None,
        year_end: Optional[int] = None,
    ) -> List[Dict]:
        """
        列出公司的 10-Q 季報（由新到舊）。

        Args:
            ticker: 股票代碼，例如 'AAPL'
            cik: 或直接給 SEC CIK（與 ticker 二擇一）
            limit: 最多幾筆（None 表示不限制，再依 year_start/year_end 篩選）
            year_start: 只保留此年（含）之後的申報日
            year_end: 只保留此年（含）之前的申報日

        Returns:
            列表，每筆含 filing_date, accession_number, primary_document, report_url, description
        """
        if cik is None and ticker:
            cik = self.ticker_to_cik(ticker)
        if not cik:
            return []
        data = self.get_submissions(cik)
        if not data or "filings" not in data or "recent" not in data["filings"]:
            return []
        recent = data["filings"]["recent"]
        forms = recent.get("form") or []
        dates = recent.get("filingDate") or []
        accessions = recent.get("accessionNumber") or []
        primaries = recent.get("primaryDocument") or []
        descriptions = recent.get("description") or []
        name = data.get("name") or ticker or cik

        result = []
        for i, form in enumerate(forms):
            if form != "10-Q":
                continue
            acc = accessions[i] if i < len(accessions) else ""
            acc_no_dash = acc.replace("-", "") if acc else ""
            primary = primaries[i] if i < len(primaries) else ""
            desc = descriptions[i] if i < len(descriptions) else ""
            filing_date = dates[i] if i < len(dates) else ""
            if not acc_no_dash or not primary:
                continue
            if year_start is not None or year_end is not None:
                try:
                    y = int(filing_date[:4]) if filing_date else 0
                    if year_start is not None and y < year_start:
                        continue
                    if year_end is not None and y > year_end:
                        continue
                except (ValueError, TypeError):
                    continue
            cik_numeric = cik.lstrip("0") or "0"
            report_url = f"{SEC_ARCHIVES}/{cik_numeric}/{acc_no_dash}/{primary}"
            result.append({
                "ticker": ticker,
                "cik": cik,
                "company_name": name,
                "form": "10-Q",
                "filing_date": filing_date,
                "accession_number": acc,
                "primary_document": primary,
                "description": desc or "",
                "report_url": report_url,
            })
            if limit is not None and len(result) >= limit:
                break
        return result

    def get_latest_10q_url(
        self,
        ticker: Optional[str] = None,
        cik: Optional[str] = None,
    ) -> Optional[str]:
        """取得最近一筆 10-Q 的報告網址（直接可開的 HTML）。"""
        rows = self.list_10q(ticker=ticker, cik=cik, limit=1)
        if not rows:
            return None
        return rows[0].get("report_url")

    def download_10q(
        self,
        report_url: str,
        save_dir: Optional[Path] = None,
        filename: Optional[str] = None,
    ) -> Optional[Path]:
        """
        下載單一 10-Q 報告（HTML）到本地。

        Args:
            report_url: list_10q 回傳的 report_url
            save_dir: 存檔目錄，預設為專案下 financial_statement/downloads
            filename: 檔名，不給則依 URL 自動產生

        Returns:
            存檔路徑，失敗回傳 None
        """
        if save_dir is None:
            save_dir = Path(__file__).resolve().parent / "downloads"
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)
        if not filename:
            # 從 URL 取最後一段當檔名
            filename = report_url.strip("/").split("/")[-1]
        filepath = save_dir / filename
        r = self.session.get(
            report_url,
            headers={"User-Agent": self._user_agent, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
            timeout=60,
        )
        if not r.ok:
            return None
        filepath.write_bytes(r.content)
        return filepath

    def fetch_and_save_latest_10q(
        self,
        ticker: str,
        save_dir: Optional[Path] = None,
    ) -> Optional[Path]:
        """
        抓取指定公司最近一筆 10-Q 並存到 save_dir。

        Args:
            ticker: 股票代碼，例如 'AAPL'
            save_dir: 存檔目錄

        Returns:
            存檔路徑，無 10-Q 或下載失敗回傳 None
        """
        url = self.get_latest_10q_url(ticker=ticker)
        if not url:
            return None
        time.sleep(0.2)
        if save_dir is None:
            save_dir = Path(__file__).resolve().parent / "downloads"
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{ticker.upper()}_10Q_latest.html"
        return self.download_10q(report_url=url, save_dir=save_dir, filename=filename)
