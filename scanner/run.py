"""Bounded SEC-wide Form 4 monitor, public data + transparent coverage counters.

Scheduled runs discover filings through SEC EDGAR daily indexes, not a watchlist.
Because free quotas and SEC indexing are finite, NEVER imply instantaneous/full coverage.
"""
from __future__ import annotations
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from scanner.fundamentals import summarize_company_facts
from scanner.notifications import send_telegram
from scanner.parser import parse_form4
from scanner.identity import filing_key, normalize_events
from scanner.scoring import screen
from scanner.sec import company_facts, get, recent_entries

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
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


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
    entries, checked, errors = recent_entries(days=days)
    if not checked:
        old.update(last_attempt_utc=now, status='Errore: indici SEC non accessibili', errors=errors[:25])
        save_json(RESULTS, old)
        print('SEC index unavailable: ' + '; '.join(errors), file=sys.stderr)
        sys.exit(2)

    pending = [x for x in entries if filing_key(x['url']) not in seen]
    pending.sort(key=lambda x: (x['filed'], x['url']), reverse=True)
    queue = pending[:limit]
    purchases, processed_success = [], 0
    for filing in queue:
        try:
            txs = parse_form4(get(filing['url']), filing)
            # Source may include fund/private issuer; don't invent a US-listed ticker.
            purchases.extend(x for x in txs if x['cik'] and re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,9}', x['symbol']))
            seen.add(filing_key(filing['url']))
            processed_success += 1
        except Exception as exc:
            errors.append(f"Form 4 {filing['url']}: {type(exc).__name__}: {str(exc)[:85]}")

    historical = load_json(HISTORY, {'filings': []})
    merged = {x['id']: x for x in normalize_events(historical.get('filings', []))}
    merged.update({x['id']: x for x in purchases})
    events = list(merged.values())
    facts_cache = {}
    for p in purchases:
        cik = p['cik']
        key = (cik, p['filed'])
        if key not in facts_cache:
            try:
                facts_cache[key] = summarize_company_facts(company_facts(cik), p['filed'])
            except Exception as exc:
                facts_cache[key] = None
                errors.append(f"Companyfacts CIK {cik}: {type(exc).__name__}: {str(exc)[:75]}")
        p['fundamentals'] = facts_cache[key]
        p['analysis'] = screen(p, p['fundamentals'], distinct_insiders_near(p, events))
        merged[p['id']] = p

    for event in merged.values():
        event['analysis'] = screen(event, event.get('fundamentals'), distinct_insiders_near(event, list(merged.values())))

    ordered = sorted(merged.values(), key=lambda x: (x.get('filed', ''), x.get('amount', 0)), reverse=True)
    # Keep several years of actual source events for eventual historical research.
    save_json(HISTORY, {'version': 1, 'filings': ordered[:15_000]})
    recent = ordered[:800]
    for x in purchases:
        if not x['analysis']['notify'] or x['id'] in notified:
            continue
        # No old catch-up alerts on first setup, unless explicitly opted in.
        if x['filed'] < now[:10] and os.getenv('ALERT_HISTORICAL') != 'true':
            continue
        try:
            if send_telegram(x):
                notified.add(x['id'])
        except Exception as exc:
            errors.append(f"Telegram {x['id'][:35]}: {type(exc).__name__}: {str(exc)[:75]}")
    model = load_json(MODEL, {})
    model_status = (f"Sperimentale — validazione cronologica su {model.get('test_count')} esempi; "
                    f"NON è un segnale BUY" if model.get('validated')
                    else 'NON addestrato/validato — punteggio basato su regole')
    data = {
        'version': 1, 'last_scan_utc': now,
        'status': 'Parziale' if errors or any(filing_key(x['url']) not in seen for x in entries) else 'Finestra processata',
        'source': 'SEC EDGAR index + SEC Form 4 + SEC XBRL companyfacts',
        'model_status': model_status,
        'coverage': {'days_checked': checked, 'form4_listed_in_checked_days': len(entries),
                     'new_forms_this_run': processed_success,
                     'unprocessed_listed_forms': sum(filing_key(x['url']) not in seen for x in entries),
                     'lookback_days': days,
                     'transactions_stored': len(ordered),
                     'note': 'Non equivale a copertura totale o in tempo reale dei mercati USA'},
        'errors': errors[:25], 'filings': recent,
    }
    save_json(RESULTS, data)
    # Sort deterministic: most recent known forms kept for dedup (not random order).
    known = {filing_key(x['url']) for x in entries if filing_key(x['url']) in seen}
    older = sorted(seen - known, reverse=True)
    save_json(STATE, {'processed': sorted(known, reverse=True) + older[:20_000],
                      'notified': sorted(notified)[-5_000:]})
    print(f'SEC: {len(entries)} indexed Form 4; {processed_success} processed; {len(purchases)} purchases; '
          f'{len(ordered)} history; {len(errors)} errors; {data["coverage"]["unprocessed_listed_forms"]} pending')


if __name__ == '__main__':
    main()
