"""SEC-only preliminary ranking: never substitutes for verified selection."""
import math


def rank(companies, reviews):
    rows = []
    for c in companies:
        if c.get('selection_status') != 'pending' or not c.get('aggregation_verified') or c['amount'] < 100_000:
            continue
        r = reviews[c['cik']]
        fields = ('id', 'cik', 'symbol', 'company', 'window_start', 'window_end', 'amount',
                  'transaction_count', 'reported_transaction_count', 'aggregation_verified',
                  'weighted_price', 'historical_market_cap', 'historical_market_cap_as_of',
                  'market_cap', 'current_price', 'current_price_as_of', 'detail_url',
                  'selection_status', 'significant_window_count', 'selection_reasons', 'insider_roles')
        row = {k: c.get(k) for k in fields}
        row['preliminary'] = True
        # Data-quality triage only: preserve values; never silently correct SEC units.
        row['amount_review_required'] = c['amount'] >= 1_000_000_000 or (c.get('weighted_price') or 0) >= 10_000
        row['amount_review_note'] = 'Importo estremo: verificare unità, note e corrispettivo nel Form 4 originale; valore non certificato' if row['amount_review_required'] else None
        row['analysis'] = dict(radar_score=None, score_status='non_verificabile', quality_pass=False,
                               insider_strength_score=c.get('analysis', {}).get('insider_strength_score'))
        row['sec_observations'] = sum(v is not None for v in r['annual'].values())
        row['sec_risks'] = r['risks']
        cap = c.get('historical_market_cap')
        row['purchase_to_historical_cap_pct'] = c['amount']/cap*100 if cap and cap > 0 else None
        rows.append(row)
    # Amount is the primary factual ranking. Tie breaks are disclosed, never a financial rating.
    rows.sort(key=lambda c: (c['amount_review_required'], -c['amount'], -(c['analysis']['insider_strength_score'] or 0),
                             -c['sec_observations'], c['cik']))
    return rows


def shares_observations(raw, as_of):
    """Dated entity facts, not class-reconciled outstanding shares or a current cap."""
    result = []
    for taxonomy, tag in [('dei', 'EntityCommonStockSharesOutstanding'), ('us-gaap', 'CommonStockSharesOutstanding')]:
        rows = raw.get('facts', {}).get(taxonomy, {}).get(tag, {}).get('units', {}).get('shares', [])
        valid = [r for r in rows if isinstance(r.get('val'), (int, float)) and not isinstance(r['val'], bool)
                 and math.isfinite(r['val']) and r['val'] > 0 and not r.get('start')
                 and r.get('filed', '9999') < as_of and r.get('end', '9999') <= as_of
                 and r.get('form') in ('10-K', '10-Q', '10-K/A', '10-Q/A')]
        if valid:
            r = max(valid, key=lambda x: (x['end'], x['filed']))
            result.append({**{k: r.get(k) for k in ('val', 'end', 'filed', 'accn', 'form')},
                           'tag': tag, 'taxonomy': taxonomy, 'unit': 'shares', 'class_scope_verified': False})
    return result


def recent_filings(raw, start, as_of):
    """Index only: discovery is not substantive review of post-purchase changes."""
    recent = raw.get('filings', {}).get('recent', {})
    rows = []
    for i, form in enumerate(recent.get('form', [])):
        day = recent['filingDate'][i]
        if start <= day < as_of and form in ('8-K', '8-K/A', '10-Q', '10-K', '10-Q/A', '10-K/A', '6-K', '20-F'):
            accession = recent['accessionNumber'][i]
            rows.append(dict(form=form, filed=day, accession=accession,
                             url=f'https://www.sec.gov/Archives/edgar/data/{int(raw["cik"])}/{accession.replace("-", "")}/{accession}-index.html'))
    return dict(filings=rows[:40], total_recent_index_matches=len(rows), truncated=len(rows)>40,
                substantive_review_verified=False, coverage='Solo indice recent SEC; non garantisce tutti gli eventi o comunicati')
