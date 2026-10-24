"""Extract *actual* Form 4 non-derivative transaction code P purchases.

A filing may contain several transactions and several reporting owners. We attribute
one transaction to its reported owners but do not multiply the traded amount when
multiple owners appear on the same filing (the owners are labelled as joint).
"""
from __future__ import annotations
import re
import xml.etree.ElementTree as ET


def _get(el, path, default=""):
    node = el.find(path) if el is not None else None
    return (node.text or "").strip() if node is not None and node.text else default


def parse_form4(submission: str, filing: dict) -> list[dict]:
    # Full SEC submission contains wrapper headers and one or more XML documents.
    match = re.search(r"<ownershipDocument(?:\s[^>]*)?>.*?</ownershipDocument>", submission, re.S | re.I)
    if not match:
        return []
    try:
        root = ET.fromstring(match.group(0))
    except ET.ParseError:
        return []
    for el in root.iter():
        el.tag = el.tag.rsplit('}', 1)[-1]
    issuer = root.find('issuer')
    symbol = _get(issuer, 'issuerTradingSymbol').upper()
    issuer_cik = _get(issuer, 'issuerCik')
    company = _get(issuer, 'issuerName') or filing['company']
    owners = []
    for owner in root.findall('reportingOwner'):
        rel = owner.find('reportingOwnerRelationship')
        owners.append({
            'name': _get(owner.find('reportingOwnerId'), 'rptOwnerName') or 'Non disponibile',
            'officer': _get(rel, 'isOfficer') == '1',
            'director': _get(rel, 'isDirector') == '1',
            'ten_pct': _get(rel, 'isTenPercentOwner') == '1',
            'officer_title': _get(rel, 'officerTitle'),
        })
    if not owners:
        owners = [{'name': 'Non disponibile', 'officer': False, 'director': False,
                   'ten_pct': False, 'officer_title': ''}]
    result = []
    for idx, tx in enumerate(root.findall('./nonDerivativeTable/nonDerivativeTransaction')):
        if (_get(tx, 'transactionCoding/transactionCode') != 'P' or
                _get(tx, 'transactionAmounts/transactionAcquiredDisposedCode/value') != 'A'):
            continue
        try:
            shares = float(_get(tx, 'transactionAmounts/transactionShares/value'))
            unit_price = float(_get(tx, 'transactionAmounts/transactionPricePerShare/value'))
        except ValueError:
            continue
        if not (0 < shares < 1e13 and 0 < unit_price < 1e9):
            continue
        primary = owners[0]
        result.append({
            'id': f"{filing['url']}#tx{idx}",
            'company': company, 'symbol': symbol or 'N/D',
            'cik': int(issuer_cik) if issuer_cik.isdigit() else 0,
            'filed': filing['filed'], 'transaction_date': _get(tx, 'transactionDate/value'),
            'insider': ', '.join(o['name'] for o in owners),
            'officer_title': primary['officer_title'],
            'officer': any(o['officer'] for o in owners),
            'director': any(o['director'] for o in owners),
            'ten_pct': any(o['ten_pct'] for o in owners),
            'shares': shares, 'unit_price': unit_price,
            'amount': round(shares * unit_price, 2), 'form_url': filing['url'],
            'code': 'P', 'source': 'SEC Form 4',
            'owners': [o['name'] for o in owners],
            'transaction_footnote': 'Prezzo e quantità dichiarati nel Form 4; non necessariamente acquisto sul mercato regolamentato',
        })
    return result
