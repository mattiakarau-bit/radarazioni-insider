"""SEC public EDGAR client with conservative request throttling and explicit identity."""
from __future__ import annotations
import json
import re
from scanner.identity import filing_key, iso_date
import os
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

SEC_ROOT = "https://www.sec.gov"
FACTS_ROOT = "https://data.sec.gov"
_last_request = 0.0


def get(url: str, *, decode: bool = True):
    global _last_request
    ua = os.environ.get("SEC_USER_AGENT", "").strip()
    if "@" not in ua or len(ua) < 12:
        raise RuntimeError("Imposta SEC_USER_AGENT con nome e email reale, ad es. RadarAzioni contatto@example.com")
    if not url.startswith((SEC_ROOT + "/", FACTS_ROOT + "/")):
        raise ValueError("URL fuori da SEC: " + url)
    for attempt in range(3):
        elapsed = time.monotonic() - _last_request
        if elapsed < 0.5:
            time.sleep(0.5 - elapsed)
        _last_request = time.monotonic()
        req = urllib.request.Request(url, headers={
            "User-Agent": ua, "Accept-Encoding": "identity", "Accept": "application/json,text/plain,application/xml,*/*",
        })
        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                body = response.read(9_000_000)
            return body.decode("utf-8", "replace") if decode else body
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 404):
                raise
            if attempt == 2 or exc.code not in (429, 500, 502, 503, 504):
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(2 ** attempt * 4)


def index_url(day: date) -> str:
    qtr = (day.month - 1) // 3 + 1
    url = f"{SEC_ROOT}/Archives/edgar/daily-index/{day.year}/QTR{qtr}/master.{day:%Y%m%d}.idx"
    return url


def read_master_index(day: date) -> list[dict]:
    data = get(index_url(day))
    if "cik|companyname|formtype|datefiled|filename" not in re.sub(r"\s+", "", data).casefold():
        raise ValueError("Indice SEC incompleto o non valido")
    output = []
    for line in data.splitlines():
        parts = line.split("|")
        if len(parts) != 5 or parts[2].strip() != "4":
            continue
        cik, company, form, filed, filename = [p.strip() for p in parts]
        if not cik.isdigit() or not filename.startswith("edgar/data/"):
            continue
        output.append({"cik": int(cik), "company": company, "form": form, "filed": iso_date(filed),
                       "url": f"{SEC_ROOT}/Archives/{filename}"})
    return output


def recent_entries(days: int = 5) -> tuple[list[dict], list[str], list[str]]:
    # Master indexes are finalized on SEC's schedule; missing files aren't treated as empty market days.
    all_entries, checked, errors = [], [], []
    for delta in range(days):
        day = date.today() - timedelta(days=delta)
        if day.weekday() >= 5:
            continue
        try:
            entries = read_master_index(day)
            all_entries.extend(entries)
            checked.append(day.isoformat())
        except urllib.error.HTTPError as e:
            # A 404 on the present day may mean the daily index has not yet been published.
            errors.append(f"{day.isoformat()}: HTTP {e.code}")
        except Exception as e:
            errors.append(f"{day.isoformat()}: {type(e).__name__}: {str(e)[:150]}")
    return list({filing_key(x["url"]): x for x in all_entries}.values()), checked, errors


def company_facts(cik: int) -> dict:
    return json.loads(get(f"{FACTS_ROOT}/api/xbrl/companyfacts/CIK{cik:010d}.json"))


def discover(state, days, now):
    """Refresh recent indexes, retry failed older days, backfill one day each run."""
    today = datetime.fromisoformat(now).astimezone(ZoneInfo('America/New_York')).date()
    targets = {today - timedelta(days=i) for i in range(days)}
    cursor = date.fromisoformat(state.get('backfill_cursor', (today-timedelta(days=days)).isoformat()))
    while cursor.weekday() >= 5:
        cursor -= timedelta(days=1)
    backfill = len(state.get('pending', [])) <= 2 * max(1, min(int(os.getenv('MAX_FORMS_PER_RUN', '180')), 400))
    if backfill:
        targets.add(cursor)
    retries = set(state.get('index_retries', []))
    # Record gaps after downtime; otherwise a moving lookback can skip unseen days.
    previous = date.fromisoformat(state.get('last_discovery_day', today.isoformat()))
    for i in range(max(0, (today-previous).days)):
        missed = previous + timedelta(days=i)
        if missed.weekday() < 5:
            retries.add(missed.isoformat())
    attempts = state.setdefault('index_attempts', {})
    targets.update(date.fromisoformat(d) for d in sorted(retries, key=lambda d: (attempts.get(d, ''), d))[:3])
    entries, checked, errors = [], [], []
    indexes = state.setdefault('indexes', {})
    for day in sorted(targets, reverse=True):
        if day.weekday() >= 5:
            continue
        attempts[day.isoformat()] = now
        try:
            rows = read_master_index(day)
            entries.extend(rows)
            checked.append(day.isoformat())
            indexes[day.isoformat()] = dict(url=index_url(day), checked_utc=now,
                                           accessions=sorted({filing_key(x['url']) for x in rows}))
            retries.discard(day.isoformat())
        except Exception as exc:
            retries.add(day.isoformat())
            errors.append(f'{day}: {type(exc).__name__}: {str(exc)[:120]}')
    state['last_discovery_day'] = today.isoformat()
    state['index_retries'] = sorted(retries)
    state['backfill_cursor'] = (cursor-timedelta(days=1) if backfill else cursor).isoformat()
    return list({filing_key(x['url']): x for x in entries}.values()), checked, errors
