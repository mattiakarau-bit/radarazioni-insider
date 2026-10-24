"""Extract point-in-time annual SEC XBRL facts. Missing data is never converted into growth."""
from __future__ import annotations
from datetime import date

REVENUE_TAGS = ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet", "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueGoodsNet"]


def _annual(facts: dict, tags: list[str], unit: str, as_of: str) -> list[dict]:
    gaap = facts.get("facts", {}).get("us-gaap", {})
    for tag in tags:
        obs = gaap.get(tag, {}).get("units", {}).get(unit, [])
        values = {}
        for entry in obs:
            if entry.get("form") not in ("10-K", "10-K/A") or entry.get("fp") != "FY":
                continue
            # Conservative point-in-time test: omit same-day facts with unknown filing time.
            if entry.get("filed", "9999") >= as_of:
                continue
            # Compare genuine ~full-year durations, not accidentally quarterly values in 10-K.
            try:
                elapsed = (date.fromisoformat(entry["end"]) - date.fromisoformat(entry["start"])).days
            except (KeyError, ValueError):
                continue
            if not 300 <= elapsed <= 380:
                continue
            end_year = entry["end"][:4]
            if not end_year.isdigit():
                continue
            year = int(end_year)
            if "val" not in entry:
                continue
            if year not in values or entry["filed"] > values[year]["filed"]:
                values[year] = {"year": year, "value": entry["val"], "filed": entry["filed"]}
        if len(values) >= 2:
            return sorted(values.values(), key=lambda x: x["year"])[-5:]
    return []


def _trend(records: list[dict]):
    if len(records) < 3:
        return None
    recent = records[-4:]
    if any(recent[i]["year"] - recent[i - 1]["year"] != 1 for i in range(1, len(recent))):
        return None
    return all(recent[i]["value"] > recent[i - 1]["value"] for i in range(1, len(recent)))


def summarize_company_facts(facts: dict, as_of: str) -> dict:
    revenues = _annual(facts, REVENUE_TAGS, "USD", as_of)
    # EPS can have distinct diluted vs basic series, choose diluted if available.
    eps = _annual(facts, ["EarningsPerShareDiluted", "EarningsPerShareBasic"], "USD/shares", as_of)
    cashflow = _annual(facts, ["NetCashProvidedByUsedInOperatingActivities"], "USD", as_of)
    return {
        "revenue_years": revenues,
        "eps_years": eps,
        "cashflow_years": cashflow,
        "revenue_growing": _trend(revenues),
        "eps_growing": _trend(eps),
        "cashflow_positive": all(p["value"] > 0 for p in cashflow[-3:]) if len(cashflow) >= 3 else None,
        "company_name": facts.get("entityName"),
    }
