"""Date/class-aware calculations. No provider approval or investment certification."""
from datetime import date
from math import isfinite, prod


def number(x):
    return isinstance(x,(int,float)) and not isinstance(x,bool) and isfinite(x)


def day(x):
    try:
        d=date.fromisoformat(x)
        return d if d.isoformat()==x else None
    except (TypeError,ValueError):return None


def near_insider(transactions, prices, as_of, *, security_id, actions_reviewed=False, tolerance_pct=15):
    if not number(tolerance_pct) or not 0<=tolerance_pct<=100:raise ValueError('Invalid tolerance')
    missing=dict(status='unverified',adjusted_insider_price=None,current_price=None,difference_pct=None,within_band=None)
    if not day(as_of) or not actions_reviewed or not transactions:return missing
    if any(t.get('security_id')!=security_id or t.get('currency')!='USD' or not day(t.get('transaction_date')) or t['transaction_date']>as_of
           or not number(t.get('unit_price')) or t['unit_price']<=0 or not number(t.get('shares')) or t['shares']<=0 for t in transactions):return missing
    rows=[p for p in prices if p.get('security_id')==security_id and p.get('currency')=='USD' and day(p.get('day')) and p['day']<=as_of]
    if not rows:return missing
    if len({p['day'] for p in rows})!=len(rows):return missing
    rows.sort(key=lambda p:p['day']);latest=rows[-1]
    if not number(latest.get('close')) or latest['close']<=0 or (day(as_of)-day(latest['day'])).days>7:return missing
    first=min(t['transaction_date'] for t in transactions)
    if rows[0]['day']>first:return missing
    # Provider's adjClose also adjusts dividends: never use it for the insider cost basis.
    if any(not number(p.get('split_factor')) or p['split_factor']<=0 for p in rows):return missing
    adjusted_shares=0;cost=0
    seen=set()
    for t in transactions:
        if not t.get('id') or t['id'] in seen:return missing
        seen.add(t['id'])
        factor=prod(p['split_factor'] for p in rows if t['transaction_date']<p['day']<=latest['day'])
        adjusted_shares+=t['shares']*factor;cost+=t['shares']*t['unit_price']
    if not number(adjusted_shares) or adjusted_shares<=0 or not number(cost):return missing
    basis=cost/adjusted_shares;difference=(latest['close']/basis-1)*100
    if not number(difference):return missing
    return dict(status='calculated_personal',adjusted_insider_price=basis,current_price=latest['close'],price_as_of=latest['day'],
                exchange=latest.get('exchange'),difference_pct=difference,within_band=abs(difference)<=tolerance_pct+1e-10,
                tolerance_pct=tolerance_pct,security_id=security_id,basis='raw close and split-only adjustment; dividends excluded',
                financial_opportunity_verified=False)


def capitalization(classes, target_day, as_of, *, all_classes_review_reference):
    """Exact share-count date; no carrying July shares into October or public-float proxy."""
    fail=dict(value=None,status='unverified',missing='Complete classes, exact dates and SEC provenance required')
    if not day(target_day) or not day(as_of) or target_day>as_of or not classes or not all_classes_review_reference:return fail
    if len({c.get('security_id') for c in classes})!=len(classes):return fail
    total=0
    for c in classes:
        p,s=c.get('price',{}),c.get('shares',{})
        if (not c.get('security_id') or not c.get('class_review_reference') or p.get('security_id')!=c['security_id'] or s.get('security_id')!=c['security_id']
            or p.get('currency')!='USD' or p.get('day')!=target_day or s.get('end')!=target_day or not day(s.get('filed'))
            or s['filed']>=as_of or s['end']>s['filed'] or not s.get('source_url','').startswith('https://www.sec.gov/Archives/')
            or s.get('unit')!='shares' or s.get('tag') not in ('EntityCommonStockSharesOutstanding','CommonStockSharesOutstanding')
            or not s.get('accession') or not number(s.get('value')) or s['value']<=0 or not number(p.get('close')) or p['close']<=0):return fail
        total+=p['close']*s['value']
    if not number(total) or total<=0:return fail
    return dict(value=total,as_of=target_day,currency='USD',status='calculated_personal',
                review_reference=all_classes_review_reference,public_on=max(c['shares']['filed'] for c in classes),
                note='All reviewed classes; unadjusted close times same-date outstanding shares; not SEC public float')
