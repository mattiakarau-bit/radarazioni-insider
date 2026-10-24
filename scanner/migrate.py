"""Offline, repeatable migration; no SEC requests or notifications."""
from scanner.run import HISTORY, RESULTS, load_json, save_json, distinct_insiders_near
from scanner.identity import normalize_events
from scanner.scoring import screen
from scanner.radar import publish
from scanner.fundamentals import _trend, review_legacy


def main():
    history = load_json(HISTORY, {'filings': []})
    events = normalize_events(history['filings'])
    for event in events:
        fin = event.get('fundamentals')
        if fin:
            # Earlier compact dates could admit same-day/later financial filings.
            for key in ('revenue_years', 'eps_years', 'cashflow_years'):
                fin[key] = [p for p in fin.get(key, []) if p['filed'] < event['filed']]
            fin['revenue_growing'] = _trend(fin['revenue_years']) if fin.get('schema_version')!=2 or fin.get('revenue_scope_verified') else None
            fin['eps_growing'] = _trend(fin['eps_years'])
            cf = fin['cashflow_years'][-3:]
            fin['cashflow_positive'] = all(p['value'] > 0 for p in cf) if len(cf) == 3 and all(cf[i]['year'] - cf[i-1]['year'] == 1 for i in (1,2)) else None
        event['fundamentals'] = review_legacy(fin)
        fin = event['fundamentals']
        event['analysis'] = screen(event, fin, distinct_insiders_near(event, events))
    events.sort(key=lambda x: (x['filed'], x['amount']), reverse=True)
    history.update(version=2, filings=events)
    save_json(HISTORY, history)
    results = load_json(RESULTS, {})
    results.update(version=2, filings=events[:800])
    results.setdefault('coverage', {})['transactions_stored'] = len(events)
    save_json(RESULTS, results)
    save_json(RESULTS.parent / 'radar.json', publish(events, results.get('last_scan_utc', '')[:10]))
    print(f'Migrated {len(events)} unique transactions')

if __name__ == '__main__':
    main()
