"""
從 SEC Company Facts API 取得 XBRL 結構化財報數據（10-Q/10-K）
用於匯出至 Excel，無需解析 HTML。
"""
import os
import re
from typing import Dict, List, Optional, Tuple, Any

import requests

SEC_USER_AGENT = os.environ.get("SEC_USER_AGENT") or "Trading system (trading.system.contact@gmail.com)"
SEC_FACTS_BASE = "https://data.sec.gov/api/xbrl/companyfacts"

# 要擷取的 US-GAAP / DEI 概念（優先使用第一個名稱，若無則試下一個）
# 對應常見財報項目
CONCEPT_PRIORITY: Dict[str, List[str]] = {
    "Revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueGoodsNet", "SalesRevenueNet", "RevenueFromContractWithCustomerIncludingAssessedTax"],
    "NetIncome": ["NetIncomeLoss", "ProfitLoss"],
    "EPS_Basic": ["EarningsPerShareBasic"],
    "EPS_Diluted": ["EarningsPerShareDiluted"],
    "TotalAssets": ["Assets", "AssetsAbstract"],
    "TotalLiabilities": ["Liabilities", "LiabilitiesAbstract"],
    "StockholdersEquity": ["StockholdersEquity", "Equity", "EquityAttributableToParent", "EquityAttributableToOwnersOfParent"],
    "CashAndEquivalents": ["CashAndCashEquivalentsAtCarryingValue", "Cash", "CashAndCashEquivalents"],
    "GrossProfit": ["GrossProfit"],
    "OperatingIncome": ["OperatingIncomeLoss"],
    "CostOfRevenue": ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"],
    "ResearchAndDevelopment": ["ResearchAndDevelopmentExpense"],
    "SellingGeneralAndAdmin": ["SellingGeneralAndAdministrativeExpense", "SellingAndMarketingExpense"],
    "OperatingExpenses": ["OperatingExpenses"],
    "InterestExpense": ["InterestExpense", "InterestExpenseDebt"],
    "IncomeTaxExpense": ["IncomeTaxExpenseBenefit", "IncomeTaxExpense"],
    "DepreciationAndAmortization": ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization"],
    "SharesOutstanding": ["EntityCommonStockSharesOutstanding"],  # dei
}


def fetch_company_facts(cik: str, session: Optional[requests.Session] = None) -> Optional[Dict]:
    """取得單一公司的 Company Facts JSON。"""
    cik_clean = re.sub(r"\D", "", cik)
    if not cik_clean:
        return None
    cik_padded = cik_clean.zfill(10)
    url = f"{SEC_FACTS_BASE}/CIK{cik_padded}.json"
    sess = session or requests.Session()
    r = sess.get(url, headers={"User-Agent": SEC_USER_AGENT, "Accept": "application/json"}, timeout=60)
    if not r.ok:
        return None
    return r.json()


def _collect_facts_from_scope(
    facts_dict: Dict[str, Any],
    year_start: int,
    year_end: int,
    forms: Tuple[str, ...] = ("10-Q", "10-K"),
) -> List[Dict[str, Any]]:
    """從 facts 底下某個 scope (us-gaap / dei) 蒐集符合條件的 (concept, end, val, unit, form, filed)。"""
    out = []
    for concept_name, concept_data in (facts_dict or {}).items():
        units = concept_data.get("units") or {}
        for unit_type, entries in units.items():
            for item in entries or []:
                form = (item.get("form") or "").strip()
                if form not in forms:
                    continue
                end = item.get("end")
                if not end:
                    continue
                try:
                    y = int(str(end)[:4])
                except (ValueError, TypeError):
                    continue
                if y < year_start or y > year_end:
                    continue
                val = item.get("val")
                if val is None:
                    continue
                out.append({
                    "concept": concept_name,
                    "end": end,
                    "val": val,
                    "unit": unit_type,
                    "form": form,
                    "fy": item.get("fy"),
                    "fp": item.get("fp"),
                    "filed": item.get("filed"),
                })
    return out


def extract_quarterly_facts(
    company_facts: Dict,
    year_start: int = 2000,
    year_end: int = 2025,
    concept_priority: Optional[Dict[str, List[str]]] = None,
) -> List[Dict[str, Any]]:
    """
    從 Company Facts JSON 擷取每季/年度財報數據。
    回傳列表，每筆為 { period_end, form, fp, concept_display, value, unit }。
    """
    concept_priority = concept_priority or CONCEPT_PRIORITY
    # 建立 concept -> display_name 對照（第一個出現的 display 對應該 tag）
    tag_to_display: Dict[str, str] = {}
    for display_name, tags in concept_priority.items():
        for tag in tags:
            tag_to_display[tag] = display_name

    facts = company_facts.get("facts") or {}
    all_rows: List[Dict[str, Any]] = []
    for scope in ("us-gaap", "dei"):
        scope_facts = facts.get(scope) or {}
        for concept_name, concept_data in scope_facts.items():
            display_name = tag_to_display.get(concept_name)
            if not display_name:
                continue
            units = concept_data.get("units") or {}
            for unit_type, entries in units.items():
                for item in entries or []:
                    form = (item.get("form") or "").strip()
                    if form not in ("10-Q", "10-K"):
                        continue
                    end = item.get("end")
                    if not end:
                        continue
                    try:
                        y = int(str(end)[:4])
                    except (ValueError, TypeError):
                        continue
                    if y < year_start or y > year_end:
                        continue
                    val = item.get("val")
                    if val is None:
                        continue
                    all_rows.append({
                        "period_end": end,
                        "form": form,
                        "fp": item.get("fp") or "",
                        "fy": item.get("fy"),
                        "filed": item.get("filed") or "",
                        "concept": display_name,
                        "value": val,
                        "unit": unit_type,
                    })
    return all_rows


def facts_to_table(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    將 extract_quarterly_facts 的列表轉成「一列一期間、一欄一概念」的表格。
    同一 period_end + concept 若有多筆，保留 filed 較新的一筆。
    """
    by_key: Dict[Tuple[str, str], Dict] = {}
    for r in rows:
        key = (r["period_end"], r["concept"])
        if key not in by_key or (r.get("filed") or "") > (by_key[key].get("filed") or ""):
            by_key[key] = dict(r)

    # 所有 period_end
    periods = sorted(set(k[0] for k in by_key))
    concepts = sorted(set(k[1] for k in by_key))
    # 建表：每列 = period_end, form, fp, fy, concept1, concept2, ...
    table: List[Dict[str, Any]] = []
    for pe in periods:
        row = {"period_end": pe, "form": "", "fp": "", "fy": ""}
        for c in concepts:
            r = by_key.get((pe, c))
            if r:
                if not row["form"]:
                    row["form"] = r.get("form") or ""
                    row["fp"] = r.get("fp") or ""
                    row["fy"] = r.get("fy") if r.get("fy") is not None else ""
                row[c] = r["value"]
                row[f"{c}_unit"] = r.get("unit") or ""
            else:
                row[c] = None
                row[f"{c}_unit"] = ""
        table.append(row)
    return table
