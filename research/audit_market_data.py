"""Offline, reproducible availability audit; never supplies production market evidence.

Uses small SEC companyconcept snapshots, not quarterly insider archives. Prices and
capitalizations stay null until a compatible, validated market source is available.
Run: python -m research.audit_market_data
"""
import hashlib
import argparse
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_CIKS = (1800, 1031203, 1067983)


def refresh_sample(root=ROOT, today=None):
    """At most six small requests; seven-day cache; uses existing SEC identity.

    Explicit command only. No prices are downloaded and no insider archive is read.
    A failed refresh leaves the preceding snapshot untouched.
    """
    from scanner.sec import get
    today = today or date.today()
    for cik in SAMPLE_CIKS:
        for kind, url in (
            ('shares', f'https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/dei/EntityCommonStockSharesOutstanding.json'),
            ('identity', f'https://data.sec.gov/submissions/CIK{cik:010d}.json'),
        ):
            path = root / f'research/market-sample/{cik}-{kind}.json'
            if path.exists():
                previous = json.loads(path.read_text())
                fetched = date.fromisoformat(previous['retrieved_on'])
                if 0 <= (today - fetched).days < 7:
                    continue
            raw = get(url, decode=False)
            data = json.loads(raw)
            if int(data['cik']) != cik:
                raise ValueError('SEC CIK mismatch')
            if kind == 'identity':
                recent = data.get('filings', {}).get('recent', {})
                filings = [{key: recent[key][i] for key in (
                    'form', 'filingDate', 'reportDate', 'accessionNumber', 'primaryDocument')}
                    for i, form in enumerate(recent.get('form', []))
                    if form in ('10-K', '10-Q') and recent['filingDate'][i] <= today.isoformat()]
                data = {key: data.get(key) for key in ('cik', 'name', 'tickers', 'exchanges')}
                data['recent_periodic_filings'] = filings[:8]
            envelope = {'retrieved_on': today.isoformat(), 'source_url': url,
                        'source_response_sha256': hashlib.sha256(raw).hexdigest(),
                        'projection': kind == 'identity', 'data': data}
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps(envelope, separators=(',', ':')) + '\n')
            temporary.replace(path)


def iso(value):
    """Reject absent, non-canonical and malformed dates rather than ordering strings."""
    try:
        parsed = date.fromisoformat(value)
        return parsed.isoformat() if parsed.isoformat() == value else None
    except (TypeError, ValueError):
        return None


def reported_shares(concept, as_of):
    """Latest publicly available *reported observation*, not shares on a price date.

    The dei concept is not a guarantee that every equity class is represented.
    Never use weighted-average EPS shares, issued shares, or public float instead.
    """
    if not iso(as_of):
        raise ValueError('Invalid as_of')
    if concept.get('taxonomy') != 'dei' or concept.get('tag') != 'EntityCommonStockSharesOutstanding':
        return {'status': 'wrong_concept', 'observation': None}
    rows = []
    observations = concept.get('units', {}).get('shares', [])
    if not isinstance(observations, list):
        observations = []
    for row in observations:
        end, filed, value = row.get('end'), row.get('filed'), row.get('val')
        if (not iso(end) or not iso(filed) or end > as_of or filed > as_of
                or row.get('start') or row.get('form') not in ('10-K', '10-Q', '10-K/A', '10-Q/A')
                or isinstance(value, bool) or not isinstance(value, int) or value <= 0
                or not row.get('accn')):
            continue
        rows.append(row)
    if not rows:
        return {'status': 'no_public_observation', 'observation': None}
    latest_end = max(row['end'] for row in rows)
    rows = [row for row in rows if row['end'] == latest_end]
    # Restatements / possible class ambiguity must not silently select the largest.
    if len({row['val'] for row in rows}) != 1:
        return {'status': 'conflicting_observations', 'observation': None, 'share_date': latest_end}
    row = max(rows, key=lambda item: (item['filed'], item['accn']))
    return {'status': 'reported_only', 'observation': {
        'shares': row['val'], 'share_date': row['end'], 'public_on': row['filed'],
        'accession': row['accn'], 'form': row['form'], 'unit': 'shares',
        'age_days': (date.fromisoformat(as_of) - date.fromisoformat(row['end'])).days,
        'same_date_as_target': row['end'] == as_of,
        'class_scope_verified': False, 'split_basis_verified': False,
    }}


def audit(root=ROOT):
    report_path = root / 'docs/data/semester_report.json'
    pending_path = root / 'docs/data/pending_index.json'
    report_bytes, pending_bytes = report_path.read_bytes(), pending_path.read_bytes()
    semester, pending = json.loads(report_bytes), json.loads(pending_bytes)
    candidates = pending['companies']
    if pending['as_of'] != semester['as_of']:
        raise ValueError('Candidate/report dates differ')
    if len({row['cik'] for row in candidates}) != len(candidates):
        raise ValueError('Duplicate candidate CIK')
    if len(candidates) != semester['stats']['pending_base_candidates']:
        raise ValueError('Candidate/report counts differ')
    by_cik = {row['cik']: row for row in candidates}
    sample = []
    detail_hashes = {}
    historical_present, current_present, historical_verified, current_verified = set(), set(), set(), set()
    for candidate in candidates:
        cik = candidate['cik']
        raw = (root / f'docs/data/companies/{cik}.json').read_bytes()
        detail_hashes[str(cik)] = hashlib.sha256(raw).hexdigest()
        detail = json.loads(raw)
        if candidate.get('market_cap') is not None:
            current_present.add(cik)
            if candidate.get('market_cap_verified') is True:
                current_verified.add(cik)
        for window in detail.get('significant_windows', []):
            if window.get('historical_market_cap') is not None:
                historical_present.add(cik)
                if window.get('weekly_economic_verified') is True:
                    historical_verified.add(cik)
    for cik in SAMPLE_CIKS:
        candidate = by_cik.get(cik, {})
        snapshots = {}
        for kind in ('shares', 'identity'):
            path = root / f'research/market-sample/{cik}-{kind}.json'
            envelope = json.loads(path.read_text())
            if int(envelope['data']['cik']) != cik:
                raise ValueError('SEC CIK mismatch')
            if not envelope['source_url'].startswith('https://data.sec.gov/'):
                raise ValueError('Unexpected source')
            snapshots[kind] = envelope
        identity, shares = snapshots['identity']['data'], snapshots['shares']['data']
        dates = sorted({w['window_end'] for w in json.loads(
            (root / f'docs/data/companies/{cik}.json').read_text()
        ).get('significant_windows', [])}) if candidate else []
        # The best window is always auditable even on older detail schemas.
        dates = sorted(set(dates + ([candidate['window_end']] if candidate else [])))
        sample.append({
            'cik': cik, 'symbol': candidate.get('symbol'), 'company': candidate.get('company', identity['name']),
            'in_candidate_snapshot': bool(candidate),
            'current_tickers': identity['tickers'],
            'ticker_list_does_not_verify_historical_classes': True,
            'shares_source_url': snapshots['shares']['source_url'],
            'shares_response_sha256': snapshots['shares']['source_response_sha256'],
            'latest_periodic_filing': identity['recent_periodic_filings'][0],
            'latest_available_reported_shares': reported_shares(shares, semester['as_of']),
            'purchase_week_reported_shares': {
                day: reported_shares(shares, day) for day in dates
            },
            'historical_capitalization': None, 'current_capitalization': None,
            'capitalization_status': 'blocked_no_approved_price_source',
        })
    return {
        'schema_version': 1, 'audit_date': date.today().isoformat(),
        'snapshot_as_of': semester['as_of'],
        'semester_report_sha256': hashlib.sha256(report_bytes).hexdigest(),
        'pending_index_sha256': hashlib.sha256(pending_bytes).hexdigest(),
        'candidate_details_digest': hashlib.sha256(json.dumps(detail_hashes, sort_keys=True).encode()).hexdigest(),
        'scope': 'Availability audit only; no production evidence or filter change',
        'counts': {
            'weekly_base_candidates': len(candidates),
            'historical_cap_values_present': len(historical_present),
            'current_cap_values_present': len(current_present),
            'historical_cap_and_weekly_threshold_verified': len(historical_verified),
            'current_cap_verified': len(current_verified),
            'sample_companies': len(sample),
            'sample_with_any_reported_share_observation': sum(
                s['latest_available_reported_shares']['observation'] is not None for s in sample),
            'sample_with_verified_historical_cap': 0, 'sample_with_verified_current_cap': 0,
            'newly_verified_capitalizations': 0,
            'combined_cap_filters_verified': len(historical_verified & current_verified),
            'candidates_without_both_cap_values': len(set(by_cik) - (historical_present & current_present)),
        },
        'count_note': 'Value availability is counted separately from verified filter passes, using every candidate detail. Reported shares can be stale or class-incomplete and are not current capitalization. No cap observations added by this audit.',
        'sample': sample,
        'market_provider_enabled': None, 'production_integration_enabled': False,
        'buy_signal': False, 'notify': False,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh-sec-sample', action='store_true',
                        help='Refresh only the three-company SEC sample using SEC_USER_AGENT; never fetch prices')
    args = parser.parse_args()
    if args.refresh_sec_sample:
        refresh_sample()
    output = ROOT / 'docs/data/market_availability_report.json'
    result = audit()
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result['counts'], ensure_ascii=False))
