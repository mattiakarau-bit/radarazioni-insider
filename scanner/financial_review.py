"""Financial observations and ratios, with explicit missing-data gates.

No HTTP, price adapter, scoring change or invented denominator. Existing caches
remain useful without being re-downloaded to fill newly requested fields.
"""
from datetime import date
from math import isfinite
from scanner.scoring import valuation_valid

VERSION = 1


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def valid(row, as_of, unit='USD', annual=True):
    if not isinstance(row, dict) or not number(row.get('value')) or row.get('unit') != unit or not row.get('tag'):
        return False
    try:
        end, filed = date.fromisoformat(row['end']), date.fromisoformat(row['filed'])
        today = date.fromisoformat(as_of)
        if filed >= today or end > filed or not 0 <= (today-end).days <= 550:
            return False
        return not annual or 300 <= (end-date.fromisoformat(row['start'])).days <= 380
    except (KeyError, TypeError, ValueError):
        return False


def free_cashflow(operating, capex):
    """CFO minus cash purchases of PPE, only on identical periods/units.

    Not an FCFE calculation or an annualization of a quarterly/YTD amount.
    Negative capex is not silently turned into a positive expense with abs().
    """
    output = []
    for ocf in operating:
        matches = [c for c in capex if all(c.get(k) == ocf.get(k) for k in ('start', 'end', 'unit'))]
        if len(matches) != 1:
            continue
        investment = matches[0]
        if (investment.get('tag') != 'PaymentsToAcquirePropertyPlantAndEquipment'
                or ocf.get('tag') != 'NetCashProvidedByUsedInOperatingActivities'
                or not number(ocf.get('value')) or not number(investment.get('value'))
                or investment['value'] < 0 or ocf.get('unit') != 'USD'):
            continue
        output.append(dict(year=ocf['year'], start=ocf['start'], end=ocf['end'],
                           filed=max(ocf['filed'], investment['filed']),
                           value=ocf['value']-investment['value'], unit='USD',
                           tag='derived_CFO_minus_cash_PPE',
                           inputs=[dict(ocf), dict(investment)]))
    return output


def additional_annual_facts(raw, as_of):
    # Called only on a companyfacts response that the existing refresh already fetched.
    from scanner.fundamentals import _annual
    income = _annual(raw, ['NetIncomeLossAvailableToCommonStockholdersBasic', 'NetIncomeLoss'], 'USD', as_of)
    ocf = _annual(raw, ['NetCashProvidedByUsedInOperatingActivities'], 'USD', as_of)
    capex = _annual(raw, ['PaymentsToAcquirePropertyPlantAndEquipment'], 'USD', as_of)
    return dict(net_income_years=income, capex_years=capex,
                free_cashflow_years=free_cashflow(ocf, capex),
                additional_financial_fields_version=VERSION)


def review(snapshot, as_of, market=None, adjusted_insider_price=None):
    """Review cached facts; optional *existing typed* market evidence for tests/adapters.

    Production has no approved market source. It does not construct market records
    from saved client flags. No result here overrides the semester/score gates.
    """
    snapshot = snapshot or {}
    fin, balance = snapshot.get('financials') or {}, snapshot.get('balance') or {}
    source = snapshot.get('source_url', '')
    source_ok = source.startswith('https://data.sec.gov/api/xbrl/companyfacts/CIK')
    annual = {}
    for name, key, unit in [('revenue', 'revenue_years', 'USD'), ('net_income', 'net_income_years', 'USD'),
                            ('eps', 'eps_years', 'USD/shares'), ('operating_cashflow', 'cashflow_years', 'USD'),
                            ('capex', 'capex_years', 'USD')]:
        rows = [r for r in fin.get(key, []) if source_ok and valid(r, as_of, unit)]
        annual[name] = max(rows, key=lambda r: (r['end'], r['filed'])) if rows else None
    derived = free_cashflow(fin.get('cashflow_years', []), fin.get('capex_years', []))
    derived = [r for r in derived if source_ok and valid(r, as_of)
               and all(valid(x, as_of) for x in r['inputs'])]
    annual['free_cashflow'] = max(derived, key=lambda r: (r['end'], r['filed'])) if derived else None
    observations = {}
    for key in ('cash', 'debt_observation', 'operating_cashflow', 'net_income'):
        r = balance.get(key)
        row = dict(r, value=r.get('val')) if isinstance(r, dict) else None
        observations[key] = r if source_ok and valid(row, as_of, annual=False) else None
    pe = pfcf = distance = None
    missing, risks = [], []
    labels = dict(revenue='Ricavi annuali documentati', net_income='Utile annuale documentato',
                  eps='EPS annuale documentato', operating_cashflow='Flusso operativo annuale',
                  capex='Capex monetario con periodo coerente', free_cashflow='FCF con CFO e capex dello stesso periodo')
    for key, label in labels.items():
        if annual[key] is None:
            missing.append(label+': non disponibile o non verificabile nella cache')
    if fin.get('revenue_scope_verified') is not True:
        missing.append('Perimetro dei ricavi totali da riconciliare')
    if observations['cash'] is None:
        missing.append('Liquidità SEC datata assente o obsoleta')
    if balance.get('debt_scope_verified') is not True:
        missing.append('Debito totale e lease non riconciliati: osservazione parziale, non debito zero')
    for key, label in [('net_income', 'Utile annuale negativo'), ('eps', 'EPS annuale negativo'),
                       ('operating_cashflow', 'Cassa operativa annuale negativa'), ('free_cashflow', 'FCF annuale negativo')]:
        if annual[key] and annual[key]['value'] < 0:
            risks.append(label)
    for key, label in [('net_income', 'Ultimo utile periodico negativo'),
                       ('operating_cashflow', 'Ultima cassa operativa periodica negativa')]:
        if observations[key] and observations[key]['val'] < 0:
            risks.append(label)
    # Reuse existing verification contract. New observations never set favorable=True.
    from scanner.semester import CurrentEvidence, current_checks
    checks = current_checks(market, as_of, as_of) if isinstance(market, CurrentEvidence) else {}
    market_ok = bool(checks.get('current_valuation_verified') and valuation_valid(market.valuation, as_of))
    if market_ok:
        income, fcf = annual['net_income'], annual['free_cashflow']
        # Total-company cap / earnings available to common: no unreviewed class EPS join.
        if income and income['tag'] == 'NetIncomeLossAvailableToCommonStockholdersBasic' and income['value'] > 0:
            pe = market.valuation.market_cap/income['value']
        if fcf and fcf['value'] > 0:
            pfcf = market.valuation.market_cap/fcf['value']
        if (market.split_review_reference and number(adjusted_insider_price)
                and adjusted_insider_price > 0):
            distance = (market.current_price/adjusted_insider_price-1)*100
    else:
        missing.append('Prezzo e capitalizzazione correnti verificati assenti: P/E e P/FCF non calcolabili')
    pe = pe if number(pe) else None
    pfcf = pfcf if number(pfcf) else None
    distance = distance if number(distance) else None
    if pe is None:
        missing.append('P/E: utili positivi attribuibili agli azionisti ordinari e cap coerente necessari')
    if pfcf is None:
        missing.append('P/FCF: FCF positivo documentato e cap verificata necessari')
    if distance is None:
        missing.append('Confronto prezzo insider: prezzo corrente e base split comune non verificati')
    return dict(version=VERSION, as_of=as_of, source_url=source or None,
                snapshot_available=bool(fin), annual=annual, balance_observations=observations,
                pe_last_fiscal_year=pe, price_to_fcf_last_fiscal_year=pfcf,
                multiple_basis='Ultimo esercizio annuale documentato; non TTM, nessuna annualizzazione YTD',
                fcf_definition='Cassa operativa meno acquisti monetari di immobili/impianti/attrezzature; non FCFE',
                distance_from_adjusted_insider_pct=distance,
                financial_rule_indicators={key: fin.get(key) for key in ('revenue_growing', 'eps_growing', 'cashflow_positive')},
                missing=missing, risks=risks, status='in_verifica',
                certified_solid=False, buy_signal=False, notify=False)


def report(companies, reviews, radar):
    candidates = [c for c in companies if c.get('selection_status') in ('pending', 'selected')]
    selected = radar['groups']
    prequalified = [c for c in candidates if c.get('weekly_economic_verified') and c.get('market_cap_verified')
                    and c.get('market_cap', 0) >= 500_000_000 and c.get('current_checks', {}).get('current_price_verified')]
    counts = dict(insider_candidates=len(candidates), passed_insider_price_cap_filters=len(prequalified),
                  candidates_with_cached_financials=sum(reviews[c['cik']]['snapshot_available'] for c in candidates),
                  candidates_without_cached_financials=sum(not reviews[c['cik']]['snapshot_available'] for c in candidates),
                  prequalified_companies_financially_analyzed=len(prequalified),
                  passed_all_criteria=len(selected), homepage_companies=len({c['cik'] for c in selected}))
    for key in ('revenue', 'net_income', 'eps', 'operating_cashflow', 'capex', 'free_cashflow'):
        counts['candidates_with_'+key] = sum(reviews[c['cik']]['annual'][key] is not None for c in candidates)
    for key in ('pe_last_fiscal_year', 'price_to_fcf_last_fiscal_year', 'distance_from_adjusted_insider_pct'):
        counts['candidates_with_'+key] = sum(reviews[c['cik']][key] is not None for c in candidates)
    for key in ('cash', 'debt_observation', 'operating_cashflow', 'net_income'):
        counts['candidates_with_periodic_'+key] = sum(reviews[c['cik']]['balance_observations'][key] is not None for c in candidates)
    counts['candidates_with_observed_negative_factors'] = sum(bool(reviews[c['cik']]['risks']) for c in candidates)
    counts['homepage_preliminary_total']=radar.get('preliminary_total',0)
    counts['homepage_preliminary_initial']=len(radar.get('preliminary_groups',[]))
    return dict(version=VERSION, as_of=radar['as_of'], counts=counts,
                note='Analisi delle cache SEC aggiornate progressivamente; disponibilità distinta da verifica completa. Candidate insider distinte da società che superano prezzi/cap. Dettagli e mancanze nei JSON per CIK.',
                homepage_ciks=[c['cik'] for c in selected], buy_signal=False, notify=False)
