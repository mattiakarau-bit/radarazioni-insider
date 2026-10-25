"""Bounded SEC-wide Form 4 monitor, public data + transparent coverage counters.

Scheduled runs discover filings through SEC EDGAR daily indexes, not a watchlist.
Because free quotas and SEC indexing are finite, NEVER imply instantaneous/full coverage.
"""
from __future__ import annotations
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from scanner.fundamentals import summarize_company_facts, review_legacy
from scanner.notifications import send_telegram
from scanner.parser import parse_form4
from scanner.identity import filing_key, normalize_events
from scanner.scoring import screen
from scanner.radar import publish, aggregate
from scanner.coverage import merge_pending, select_queue, record_failure, coverage_report
from scanner.sec import company_facts, get, discover

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'docs' / 'data'
RESULTS, STATE = DATA / 'results.json', DATA / 'state.json'
HISTORY, MODEL = DATA / 'events_history.json', DATA / 'model.json'


def load_json(path, fallback):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError, ValueError):
        return fallback


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def distinct_insiders_near(event: dict, events: list[dict]) -> int:
    # Multiple reporting names can be related funds, joint filers or nominees.
    # No verified affiliation dataset is available: never claim independence.
    return 1


def main():
    now = datetime.now(timezone.utc).isoformat(timespec='seconds')
    old = load_json(RESULTS, {'filings': [], 'status': 'mai eseguito'})
    state = load_json(STATE, {'processed': [], 'notified': []})
    seen = {filing_key(x) for x in state.get('processed', [])}
    notified = {filing_key(x) + ('#' + x.rsplit('#', 1)[-1] if '#' in x else '') for x in state.get('notified', [])}
    limit = max(1, min(int(os.getenv('MAX_FORMS_PER_RUN', '180')), 400))
    days = max(2, min(int(os.getenv('LOOKBACK_DAYS', '7')), 14))
    entries, checked, errors = discover(state, days, now)
    from scanner.bulk import known_bulk_accessions  # Lazy import avoids module initialization cycles.
    bulk_known=known_bulk_accessions(ROOT)
    pending = merge_pending(state.get('pending', []), entries, seen | bulk_known)
    state['pending'] = pending
    # Persist discovery before downloads: backlog survives window expiry or interrupted runs.
    save_json(STATE, state)
    queue = select_queue(pending, limit, now[:10])
    deadline = time.monotonic() + 18 * 60
    failed = 0
    purchases, processed_success = [], 0
    for filing in queue:
        if time.monotonic() >= deadline:
            break
        try:
            txs = parse_form4(get(filing['url']), filing)
            # Source may include fund/private issuer; don't invent a US-listed ticker.
            purchases.extend(x for x in txs if x['cik'] and re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,9}', x['symbol']))
            seen.add(filing_key(filing['url']))
            processed_success += 1
        except Exception as exc:
            failed += 1
            record_failure(filing, now[:10], str(exc))
            errors.append(f"Form 4 {filing['url']}: {type(exc).__name__}: {str(exc)[:85]}")

    historical = load_json(HISTORY, {'filings': []})
    merged = {x['id']: x for x in normalize_events(historical.get('filings', []))}
    merged.update({x['id']: x for x in purchases})
    events = list(merged.values())
    # Current annotations carry their first public date; never retroactively change
    # historical eligibility before an amendment was public.
    for amended in events:
        if not amended.get('amendment'):continue
        for original in events:
            if original.get('amendment') or original['cik']!=amended['cik']:continue
            shared=set(original.get('owner_ciks',[])) & set(amended.get('owner_ciks',[]))
            if shared and (original['filed']==amended.get('original_filing_date') or original['transaction_date']==amended['transaction_date']):
                original['amendment_known_from']=min(original.get('amendment_known_from','9999'),amended['filed'])

    for event in events:
        event['fundamentals'] = review_legacy(event.get('fundamentals'))
    facts_cache = {}
    raw_facts = {}
    # Free companyfacts calls are prioritized by the known weekly purchase filter.
    # Capitalization is absent, so no issuer is claimed to pass the full filter.
    totals = {}
    refresh = []
    facts_checked = state.setdefault('facts_checked', {})
    active = aggregate(events, (date.fromisoformat(now[:10])-timedelta(days=6)).isoformat(), now[:10])
    candidates = {g['cik'] for g in active if g['amount']>=100000}
    purchase_ids = {p['id'] for p in purchases}
    for event in events:
        fin=event.get('fundamentals') or {}
        if event['id'] not in purchase_ids and event['cik'] in candidates and not fin.get('evidence_valid') and facts_checked.get(str(event['cik']), '')<now[:10]:
            refresh.append(event)
    analysis_queue = purchases + refresh
    for p in analysis_queue:
        start = (date.fromisoformat(p['transaction_date']) - timedelta(days=6)).isoformat()
        group = aggregate(events, start, p['transaction_date'])
        totals[p['id']] = next((g['amount'] for g in group if g['cik']==p['cik']), 0)
    prioritized = sorted(analysis_queue, key=lambda p: totals[p['id']], reverse=True)
    facts_limit = max(1, min(int(os.getenv('MAX_FACTS_PER_RUN', '30')), 100))
    for p in prioritized:
        cik = p['cik']
        key = (cik, p['filed'])
        if key not in facts_cache:
            try:
                if time.monotonic() >= deadline:
                    raise TimeoutError('Budget esecuzione esaurito; fondamentali non verificati')
                if cik not in raw_facts:
                    if len(raw_facts) >= facts_limit:
                        raise RuntimeError('Budget fondamentali: analisi differita, non verificata')
                    facts_checked[str(cik)] = now[:10]
                    raw_facts[cik] = None  # Cache failures too; never repeat a failing CIK per run.
                    raw_facts[cik] = company_facts(cik)
                if raw_facts[cik] is None:
                    raise RuntimeError('Companyfacts non accessibile in questa esecuzione')
                facts_cache[key] = summarize_company_facts(raw_facts[cik], p['filed'])
            except Exception as exc:
                facts_cache[key] = None
                errors.append(f"Companyfacts CIK {cik}: {type(exc).__name__}: {str(exc)[:75]}")
        if facts_cache[key] is not None:
            p['fundamentals'] = facts_cache[key]
        elif p.get('fundamentals'):
            p['fundamentals'] = dict(p['fundamentals'])
            p['fundamentals']['data_warnings'] = list(p['fundamentals'].get('data_warnings', [])) + ['Aggiornamento SEC non riuscito/differito: conservato snapshot precedente']
        else:
            p['fundamentals'] = None
        p['analysis'] = screen(p, p['fundamentals'], distinct_insiders_near(p, events))
        merged[p['id']] = p

    for event in merged.values():
        event['analysis'] = screen(event, event.get('fundamentals'), distinct_insiders_near(event, list(merged.values())))

    ordered = sorted(merged.values(), key=lambda x: (x.get('filed', ''), x.get('amount', 0)), reverse=True)
    # Keep several years of actual source events for eventual historical research.
    save_json(HISTORY, {'version': 1, 'filings': ordered})
    recent = ordered[:800]
    # Investment notifications remain disabled.
    model = load_json(MODEL, {})
    model_status = (f"Sperimentale — validazione cronologica su {model.get('test_count')} esempi; "
                    f"NON è un segnale BUY" if model.get('validated')
                    else 'NON addestrato/validato — punteggio basato su regole')
    pending = merge_pending(pending, [], seen | bulk_known)
    coverage = coverage_report(state['indexes'], seen | bulk_known, pending, checked, processed_success, failed)
    coverage['forms_already_in_structured_archives']=sum(filing_key(x['url']) in bulk_known for x in entries)
    coverage.update(lookback_days=days, transactions_stored=len(ordered),
                    index_retry_days=state['index_retries'], backfill_next_date=state['backfill_cursor'])
    data = {
        'version': 1, 'last_scan_utc': now,
        'status': 'Parziale' if errors or pending else 'Indici registrati processati',
        'source': 'SEC EDGAR index + SEC Form 4 + SEC XBRL companyfacts',
        'model_status': model_status,
        'coverage': coverage,
        'errors': errors[:25], 'filings': recent,
    }
    save_json(RESULTS.parent / 'radar.json', publish(ordered, now[:10]))
    save_json(RESULTS, data)
    state.update(processed=sorted(seen), notified=sorted(notified), pending=pending)
    save_json(STATE, state)
    print(f'SEC: {len(entries)} indexed Form 4; {processed_success} processed; {len(purchases)} purchases; '
          f'{len(ordered)} history; {len(errors)} errors; {data["coverage"]["unprocessed_listed_forms"]} pending')


if __name__ == '__main__':
    main()
