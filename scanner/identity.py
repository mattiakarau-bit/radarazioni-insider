"""Stable SEC identities: the same accession can appear under several owner CIKs."""
import re
from datetime import date


def iso_date(value):
    value = str(value or "").strip()
    if re.fullmatch(r"\d{8}", value):
        value = f"{value[:4]}-{value[4:6]}-{value[6:]}"
    return date.fromisoformat(value).isoformat()


def filing_key(url):
    match = re.search(r"(\d{10})-?(\d{2})-?(\d{6})(?:[./#]|$)", url)
    return "-".join(match.groups()) if match else url


def event_key(event):
    return filing_key(event['form_url']) + '#' + event['id'].rsplit('#', 1)[-1]


def normalize_events(events):
    merged = {}
    for event in events:
        event = dict(event)
        event['filed'] = iso_date(event['filed'])
        event['transaction_date'] = iso_date(event['transaction_date'])
        event['id'] = event_key(event)
        merged[event['id']] = event
    return list(merged.values())


def suspend_security_aliases(events):
    """Quarantine cross-filing economic matches with title variants, not add them.

    Different explicit Class A/B identifiers stay distinct. Generic vs class-specific
    or par-value spelling differences do not prove different economic purchases.
    Raw rows remain available. This establishes no reporting-owner independence.
    """
    from collections import defaultdict
    buckets=defaultdict(list)
    for row in events:
        if row.get('shares') is not None and row.get('unit_price') is not None:
            buckets[(row['cik'],row['transaction_date'],row['shares'],row['unit_price'])].append(row)
    affected=set()
    def security_class(row):
        m=re.search(r'\bclass\s+([a-z0-9]+)\b',row.get('security_title','').casefold())
        return m.group(1) if m else None
    for rows in buckets.values():
        if len({r.get('security_title','').casefold().strip() for r in rows})<2:continue
        for i,a in enumerate(rows):
            for b in rows[i+1:]:
                if filing_key(a['form_url'])==filing_key(b['form_url']):continue
                if a.get('security_title','').casefold().strip()==b.get('security_title','').casefold().strip():continue
                ac,bc=security_class(a),security_class(b)
                if ac is not None and bc is not None and ac!=bc:continue
                affected.update((a['id'],b['id']))
    changed=0
    for row in events:
        if row['id'] in affected:
            if row.get('purchase_eligible'):changed+=1
            row['purchase_eligible']=False
            row['review_reasons']=sorted(set(row.get('review_reasons',[])+['possible_security_title_alias_co_report']))
    return changed
