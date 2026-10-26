"""SEC-only preliminary ranking: never substitutes for verified selection."""
import math


def sec_fundamental_triage(financial_review):
    """Compact, dated SEC *observations*, not a valuation or investment score."""
    annual = financial_review.get('annual') or {}
    values = {}
    for key in ('revenue', 'net_income', 'eps', 'operating_cashflow', 'free_cashflow'):
        row = annual.get(key)
        if isinstance(row, dict) and isinstance(row.get('value'), (int, float)) and math.isfinite(row['value']):
            values[key] = {field: row.get(field) for field in ('value', 'end', 'filed', 'tag', 'unit')}
        else:
            values[key] = None
    indicators = financial_review.get('financial_rule_indicators') or {}
    positives = []
    if indicators.get('revenue_growing') is True and values['revenue']:
        positives.append('Ricavi in crescita negli esercizi osservati')
    if values['eps'] and values['eps']['value'] > 0:
        positives.append('EPS annuale positivo')
    if values['operating_cashflow'] and values['operating_cashflow']['value'] > 0:
        positives.append('Cassa operativa annuale positiva')
    if values['free_cashflow'] and values['free_cashflow']['value'] > 0:
        positives.append('FCF annuale positivo (cassa operativa meno capex)')
    negatives = list(financial_review.get('risks') or [])
    coverage = sum(v is not None for v in values.values())
    # No claim of "financially strong"; a positive annual observation can still
    # coexist with poor valuation, sector-specific debt or adverse new filings.
    reviewed = coverage >= 3 and len(positives) >= 2 and not negatives
    return dict(annual=values, available_count=coverage, positive_observations=positives,
                observed_risks=negatives, sec_documented_for_review=reviewed,
                label=('Bilanci SEC utili per approfondire' if reviewed else
                       'Bilanci SEC parziali o segnali da verificare'),
                note='Solo osservazioni annuali SEC datate; nessuna capitalizzazione, prezzo, giudizio di convenienza o BUY.')


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
        evidence = sec_fundamental_triage(r)
        row['sec_evidence'] = evidence
        row['sec_observations'] = evidence['available_count']
        row['sec_risks'] = evidence['observed_risks']
        cap = c.get('historical_market_cap')
        row['purchase_to_historical_cap_pct'] = c['amount']/cap*100 if cap and cap > 0 else None
        rows.append(row)
    # Evidence-first triage (NOT a financial score). Never rank a 10-K-less
    # billion-dollar outlier ahead of candidates just because of its price.
    # Missing SEC evidence is not a negative financial finding.
    rows.sort(key=lambda c: (
        c['amount_review_required'],
        not c['sec_evidence']['sec_documented_for_review'],
        bool(c['sec_risks']),
        -len(c['sec_evidence']['positive_observations']),
        -c['sec_observations'],
        -(c['analysis']['insider_strength_score'] or 0),
        -c['amount'],
        c['cik']
    ))
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
