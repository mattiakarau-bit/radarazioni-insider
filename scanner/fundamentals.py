"""Extract point-in-time annual SEC XBRL facts. Missing data is never converted into growth."""
from __future__ import annotations
from datetime import date
import math

EXTRACTOR_VERSION = 3

REVENUE_TAGS = ["Revenues", "SalesRevenueNet", "RevenueFromContractWithCustomerExcludingAssessedTax", "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueGoodsNet"]


def _annual(facts: dict, tags: list[str], unit: str, as_of: str) -> list[dict]:
    gaap = facts.get("facts", {}).get("us-gaap", {})
    candidates = []
    for priority, tag in enumerate(tags):
        obs = gaap.get(tag, {}).get("units", {}).get(unit, [])
        values = {}
        for entry in obs:
            if entry.get("form") not in ("10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A") or entry.get("fp") != "FY":
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
            if not isinstance(entry.get("val"), (int, float)) or not math.isfinite(entry["val"]):
                continue
            if year not in values or entry["filed"] > values[year]["filed"]:
                values[year] = {"year": year, "value": entry["val"], "filed": entry["filed"], "start": entry["start"], "end": entry["end"], "tag": tag, "unit": unit}
        if len(values) >= 2:
            series = sorted(values.values(), key=lambda x: x["year"])[-5:]
            candidates.append((series[-1]["end"], -priority, series))
    # A retired concept must not hide a newer annual series. Keep each series
    # concept-pure; tie-break by explicit tag priority and retain scope checks.
    return max(candidates, key=lambda x:(x[0],x[1]))[2] if candidates else []


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
    # Contract-customer revenue can exclude rental/interest income. Never silently
    # promote such a partial series to total revenue when competing series disagree.
    alternatives = [_annual(facts, [tag], "USD", as_of) for tag in REVENUE_TAGS]
    conflict = any(abs(a['value']-b['value']) > max(abs(a['value']),abs(b['value']),1)*0.05
                   for series in alternatives for a in revenues for b in series if a['year']==b['year'])
    financial_tags = set(facts.get('facts',{}).get('us-gaap',{}))
    restricted_scope = revenues and revenues[-1]['tag'].startswith('RevenueFromContract') and bool(
        financial_tags & {'InterestIncomeExpenseNet','InterestAndDividendIncomeOperating','OperatingLeaseLeaseIncome'})
    scope_ok = bool(revenues) and not conflict and not restricted_scope
    warnings = []
    if not scope_ok:
        warnings.append('Ricavi totali non riconciliati: serie assente, parziale o tag discordanti')
    def fresh(series):
        return bool(series) and 0 <= (date.fromisoformat(as_of)-date.fromisoformat(series[-1]['end'])).days <= 550
    return {
        "schema_version": 2, "extractor_version": EXTRACTOR_VERSION, "revenue_years": revenues, "eps_years": eps, "cashflow_years": cashflow,
        "revenue_scope_verified": scope_ok,
        "revenue_growing": _trend(revenues) if scope_ok else None,
        "eps_growing": _trend(eps),
        "cashflow_positive": all(p["value"] > 0 for p in cashflow[-3:]) if len(cashflow)>=3 and all(cashflow[i]["year"]-cashflow[i-1]["year"]==1 for i in range(len(cashflow)-2,len(cashflow))) else None,
        "eps_latest_positive": eps[-1]['value']>0 if eps else None,
        "cashflow_latest_positive": cashflow[-1]['value']>0 if cashflow else None,
        "fresh": all(fresh(x) for x in (revenues,eps,cashflow)),
        "evidence_valid": bool(scope_ok and all(x for x in (revenues,eps,cashflow))),
        "as_of": as_of, "source_url": "https://data.sec.gov/api/xbrl/companyfacts/", "data_warnings": warnings,
        "company_name": facts.get("entityName"),
    }


def review_legacy(fin):
    """Keep original series; old snapshots lack tags/end dates and cannot prove scope."""
    if not fin or fin.get('schema_version') == 2:
        return fin
    fin = dict(fin)
    fin.setdefault('legacy_indicators', {k:fin.get(k) for k in ('revenue_growing','eps_growing','cashflow_positive')})
    fin.update(schema_version=1, evidence_valid=False, fresh=None, revenue_scope_verified=False,
               revenue_growing=None,
               eps_latest_positive=fin['eps_years'][-1]['value']>0 if fin.get('eps_years') else None,
               cashflow_latest_positive=fin['cashflow_years'][-1]['value']>0 if fin.get('cashflow_years') else None,
               data_warnings=['Snapshot precedente senza tag e date di fine periodo: ricavi da riconciliare con il bilancio completo'])
    return fin
