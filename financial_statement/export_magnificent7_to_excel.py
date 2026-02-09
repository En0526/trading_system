"""
將美股七巨頭 2000~2025 每季財報內的 XBRL 數據匯出成 Excel。
存檔路徑：C:\\trading_system\\financial_statement\\Data\\
每個公司一個工作表，另有一個「總覽」表列出所有公司欄位說明。
並自動計算：負債比率、毛利率、淨利率、營業利益率、ROE 等。
"""
import sys
import time
from pathlib import Path
from typing import Dict, List

# 專案根目錄
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = Path(r"C:\trading_system\financial_statement\Data")
MAGNIFICENT_7 = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]

# 要計算的比率：(Excel 欄名, 分子欄位, 分母欄位, 是否為 %，True 則乘 100)
RATIO_DEFINITIONS = [
    ("負債比率", "TotalLiabilities", "TotalAssets", False),  # 小數，例 0.65
    ("毛利率_%", "GrossProfit", "Revenue", True),
    ("淨利率_%", "NetIncome", "Revenue", True),
    ("營業利益率_%", "OperatingIncome", "Revenue", True),
    ("ROE_%", "NetIncome", "StockholdersEquity", True),  # 股東權益報酬率
    ("營業費用率_%", "OperatingExpenses", "Revenue", True),
    ("研發費用率_%", "ResearchAndDevelopment", "Revenue", True),
    ("銷管費用率_%", "SellingGeneralAndAdmin", "Revenue", True),
]


def add_ratio_columns(df):  # pandas DataFrame
    """在 DataFrame 上依既有欄位計算比率，新增欄位（負債比率、毛利率等）。"""
    import pandas as pd
    base_cols = ["period_end", "form", "fp", "fy"]
    for label, num_col, denom_col, as_pct in RATIO_DEFINITIONS:
        if num_col not in df.columns or denom_col not in df.columns:
            continue
        num = pd.to_numeric(df[num_col], errors="coerce")
        denom = pd.to_numeric(df[denom_col], errors="coerce")
        mask = denom.notna() & (denom != 0) & num.notna()
        ratio = num / denom
        if as_pct:
            ratio = ratio * 100
        df[label] = ratio.where(mask)
    return df


def main():
    sys.path.insert(0, str(PROJECT_ROOT))
    import pandas as pd
    from financial_statement.sec_10q_fetcher import SEC10QFetcher
    from financial_statement.sec_company_facts import (
        fetch_company_facts,
        extract_quarterly_facts,
        facts_to_table,
        CONCEPT_PRIORITY,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fetcher = SEC10QFetcher()
    session = fetcher.session

    # 先建「總覽」：列出我們擷取的概念 + 計算比率說明
    overview_rows = []
    for display_name, tags in CONCEPT_PRIORITY.items():
        overview_rows.append({"財報項目(Excel欄名)": display_name, "SEC XBRL標籤(優先順序)": ", ".join(tags), "類型": "原始數據"})
    for label, num_col, denom_col, as_pct in RATIO_DEFINITIONS:
        unit = "%" if as_pct else "小數"
        overview_rows.append({"財報項目(Excel欄名)": label, "SEC XBRL標籤(優先順序)": f"{num_col} / {denom_col}", "類型": f"計算比率 ({unit})"})
    df_overview = pd.DataFrame(overview_rows)

    all_sheets: Dict[str, pd.DataFrame] = {"總覽_欄位說明": df_overview}
    name_by_ticker: Dict[str, str] = {}

    for ticker in MAGNIFICENT_7:
        print(f"[{ticker}] 取得 CIK 與 Company Facts...")
        cik = fetcher.ticker_to_cik(ticker)
        if not cik:
            print(f"  找不到 {ticker} 的 CIK，略過")
            continue
        time.sleep(0.3)
        facts = fetch_company_facts(cik, session=session)
        if not facts:
            print(f"  無法取得 {ticker} Company Facts，略過")
            continue
        entity_name = (facts.get("entityName") or ticker).strip()
        name_by_ticker[ticker] = entity_name
        print(f"  {entity_name}，擷取 2000~2025 季報數據...")
        rows = extract_quarterly_facts(facts, year_start=2000, year_end=2025)
        if not rows:
            print(f"  無符合條件的數據，略過")
            continue
        table = facts_to_table(rows)
        # 轉成 DataFrame：每列一期間，每欄一概念
        df = pd.DataFrame(table)
        # 計算比率（負債比率、毛利率、淨利率、營業利益率、ROE 等）
        df = add_ratio_columns(df)
        # 欄位排序：period_end, form, fp, fy → 原始數值欄 → 比率欄 → _unit 欄
        value_cols = [c for c in df.columns if c not in ("period_end", "form", "fp", "fy") and not c.endswith("_unit") and c not in [r[0] for r in RATIO_DEFINITIONS]]
        ratio_cols = [r[0] for r in RATIO_DEFINITIONS if r[0] in df.columns]
        unit_cols = [c for c in df.columns if c.endswith("_unit")]
        df = df[["period_end", "form", "fp", "fy"] + sorted(value_cols) + ratio_cols + sorted(unit_cols)]
        sheet_name = entity_name[:31]  # Excel 工作表名稱最長 31
        all_sheets[sheet_name] = df
        print(f"  共 {len(df)} 筆期間")

    if len(all_sheets) <= 1:
        print("無任何公司數據可寫入。")
        return

    out_file = OUTPUT_DIR / "Magnificent7_10Q_2000_2025.xlsx"
    print(f"\n寫入 Excel: {out_file}")
    with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
        for sheet_name, df in all_sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    print("完成。")


if __name__ == "__main__":
    main()
