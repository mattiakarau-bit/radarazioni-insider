"""Conservative issuer/window aggregation. Raw SEC records are never removed."""
from collections import defaultdict
from datetime import date, timedelta
from calendar import monthrange
from math import isfinite
from scanner.identity import event_key, filing_key
from scanner.scoring import screen

DEFAULT_FILTERS = dict(min_market_cap=500_000_000, min_weekly_amount=100_000,
                       proportional_pct=0.002, proportional_cap=2_000_000)


def filter_result(amount, market_cap=None, params=None):
    p = dict(DEFAULT_FILTERS, **(params or {}))
    if any(not isinstance(v, (int, float)) or not isfinite(v) or v < 0 for v in p.values()):
        raise ValueError('Parametri filtri non validi')
    if market_cap is None or not isfinite(market_cap) or market_cap <= 0:
        return dict(status='non_verificabile', required_amount=None, market_cap=None,
                    base_amount_pass=amount >= p['min_weekly_amount'])
    threshold = max(p['min_weekly_amount'], min(p['proportional_cap'], market_cap*p['proportional_pct']/100))
    return dict(status='supera' if market_cap >= p['min_market_cap'] and amount >= threshold else 'escluso',
                required_amount=threshold, market_cap=market_cap, base_amount_pass=amount >= p['min_weekly_amount'])


def _economic_key(x):
    return (x.get('transaction_date'), x.get('security_title', '').strip().casefold(),
            x.get('shares'), x.get('unit_price'))


def aggregate(events, start, end):
    unique = {}
    for x in events:
        if start <= x.get('transaction_date', '') <= end and x.get('cik'):
            unique[event_key(x)] = x
    issuers = defaultdict(list)
    for x in unique.values():
        issuers[x['cik']].append(x)
    groups = []
    for cik, rows in issuers.items():
        buckets = defaultdict(lambda: defaultdict(list))
        for x in rows:
            buckets[_economic_key(x)][filing_key(x['form_url'])].append(x)
        counted, uncertain = [], []
        for files in buckets.values():
            # Same economic terms across filings may be co-reported. Count the maximum
            # number of distinct rows in ONE filing as a conservative lower estimate.
            # Different rows within the same filing stay distinct. Never erase raw rows.
            representative = max(files.values(), key=lambda xs: (len(xs), xs[0]['id']))
            counted.extend(representative)
            if len(files) > 1:
                uncertain.extend(x['id'] for xs in files.values() for x in xs)
        latest = max(rows, key=lambda x: (x['filed'], x['id']))
        amount = round(sum(x['amount'] for x in counted), 2)
        fin = latest.get('fundamentals')
        # Group role evidence from actual reported roles; no independence bonus.
        synthetic = dict(latest, amount=amount, officer=any(x.get('officer') for x in rows),
                         director=any(x.get('director') for x in rows))
        titles = [x.get('officer_title', '') for x in rows]
        synthetic['officer_title'] = ' / '.join(titles)
        analysis = screen(synthetic, fin)
        if uncertain:
            analysis['warnings'].append('Possibili co-dichiarazioni: importo e conteggio sono stime prudenziali, non totale verificato')
        classes = {x.get('security_title', '').strip().casefold() for x in counted}
        homogeneous = len(classes) == 1 and '' not in classes and not uncertain
        shares = sum(x['shares'] for x in counted)
        groups.append(dict(id=f'{cik}:{start}:{end}', cik=cik, symbol=latest['symbol'], company=latest['company'],
                           window_start=start, window_end=end, amount=amount,
                           reported_amount=round(sum(x['amount'] for x in rows), 2),
                           transaction_count=len(counted), reported_transaction_count=len(rows),
                           aggregation_verified=not uncertain, possible_duplicate_ids=sorted(set(uncertain)),
                           independent_insiders=None, independence_verified=False,
                           weighted_price=amount/shares if homogeneous and shares else None,
                           price_basis='raw_SEC_not_split_adjusted', security_title=latest.get('security_title'),
                           market_cap=None, market_status='Fonte redistribuibile non integrata',
                           filters=filter_result(amount), analysis=analysis,
                           fundamentals=fin, fundamentals_as_of=latest['filed'],
                           transactions=sorted(rows, key=lambda x: (x['transaction_date'],x['id']), reverse=True)))
    return sorted(groups, key=lambda x: (x['analysis']['radar_score'], x['amount']), reverse=True)


def months_before(day, months):
    year, month = divmod(day.year*12+day.month-1-months, 12)
    return date(year, month+1, min(day.day, monthrange(year, month+1)[1]))


def historical_windows(events, as_of, months=6):
    if months not in (6, 12):
        raise ValueError('Periodo supportato: 6 o 12 mesi')
    today = date.fromisoformat(as_of)
    start = months_before(today, months).isoformat()
    anchors = sorted({x['transaction_date'] for x in events if start <= x.get('transaction_date','') <= as_of})
    result = []
    for end in anchors:
        begin = max(start, (date.fromisoformat(end)-timedelta(days=6)).isoformat())
        for g in aggregate(events, begin, end):
            # One window per issuer per actual transaction-date anchor; windows overlap.
            if not any(x['transaction_date']==end for x in g['transactions']):
                continue
            g['historical_review'] = historical_review(g, None, as_of)
            result.append(g)
    return result


def historical_review(group, evidence, as_of):
    """Prepared evidence gate, no downloader. Prices must share the current split basis.

    evidence is an internal adapter contract, never a client-provided verification flag.
    Corporate events/fundamentals/reasons must be researched separately even if price matches.
    """
    blocked = dict(status='non_verificabile', within_band=None, distance_pct=None,
                   buy_signal=False, notify=False,
                   pending_checks=['Prezzo corrente e rettifiche split', 'Fondamentali aggiornati',
                                   'Eventi societari e motivi del ribasso'])
    if not evidence or not group.get('aggregation_verified') or group.get('weighted_price') is None:
        return blocked
    # No provider has yet been approved for redistribution; this gate is deliberately closed.
    return blocked


def price_band(current, adjusted_insider_average):
    """Pure comparison for future validated adapters; never an investment signal."""
    if any(not isinstance(x, (int,float)) or not isfinite(x) or x <= 0 for x in (current,adjusted_insider_average)):
        return None
    distance = (current/adjusted_insider_average-1)*100
    return dict(within_band=abs(distance) <= 5+1e-9, distance_pct=round(distance,4))


def publish(events, as_of):
    events = [x for x in events if x.get('filed', '') <= as_of]
    start = (date.fromisoformat(as_of)-timedelta(days=6)).isoformat()
    return dict(version=1, app_version='0.5.0', as_of=as_of, window_start=start,
                filters=DEFAULT_FILTERS, groups=aggregate(events,start,as_of),
                history_months_available=12,
                history_status='Prezzi, split, fondamentali aggiornati ed eventi non verificati; nessuna segnalazione reale',
                historical_windows=[dict({k:v for k,v in g.items() if k not in ('transactions','fundamentals')}, transaction_ids=[x['id'] for x in g['transactions']]) for g in historical_windows(events,as_of,12)])
