"""Six-calendar-month selection, with seven-day windows and one row per issuer.

All aggregation runs in Python. Financial/market evidence is kept separate from
as-filed transactions. No market provider is implicitly approved by JSON flags.
"""
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from math import isfinite
from scanner.radar import aggregate, months_before, filter_result, DEFAULT_FILTERS
from scanner.scoring import screen, ValuationEvidence, valuation_valid
from scanner.identity import suspend_security_aliases

FORM4_CURRENCY_SOURCE='https://www.sec.gov/files/form4.pdf'

@dataclass(frozen=True)
class Capitalization:
    value: float
    as_of: str
    source_url: str
    review_reference: str
    currency: str='USD'

@dataclass(frozen=True)
class CurrentEvidence:
    financials: dict=field(default_factory=dict)
    valuation: ValuationEvidence|None=None
    historical_caps: dict=field(default_factory=dict)
    current_price: float|None=None
    price_as_of: str|None=None
    price_source: str=''
    # Values on the SAME split basis as current_price, indexed by window end.
    adjusted_insider_prices: dict=field(default_factory=dict)
    split_review_reference: str=''
    balance_sheet_review_as_of: str|None=None
    debt_review_pass: bool=False
    changes_review_start: str|None=None
    changes_review_as_of: str|None=None
    review_reference: str=''


def positive(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and isfinite(x) and x>0

def recent(day,as_of,age=7):
    try:return 0<=(date.fromisoformat(as_of)-date.fromisoformat(day)).days<=age
    except (TypeError,ValueError):return False


def cap_valid(cap,end):
    return (isinstance(cap,Capitalization) and positive(cap.value) and cap.currency=='USD'
            and recent(cap.as_of,end) and cap.source_url.startswith('https://') and bool(cap.review_reference))


def issuer_windows(rows,as_of,months=6):
    """Canonical rolling windows ending on each purchase date, clipped to search period.

    With positive purchases these include every maximal distinct seven-day purchase
    set. Empty-day duplicates are omitted; overlapping windows must never be summed.
    """
    first=months_before(date.fromisoformat(as_of),months).isoformat()
    rows=[x for x in rows if first<=x.get('transaction_date','')<=as_of and x.get('filed','9999')<=as_of]
    output=[]
    by_issuer=defaultdict(list)
    for x in rows:by_issuer[x['cik']].append(x)
    for cik,issuer_rows in sorted(by_issuer.items()):
        for end in sorted({x['transaction_date'] for x in issuer_rows}):
            start=max(first,(date.fromisoformat(end)-timedelta(days=6)).isoformat())
            groups=aggregate(issuer_rows,start,end)
            if groups and any(x['transaction_date']==end for x in groups[0]['transactions']):output.extend(groups)
    return output


def current_checks(e,as_of,first):
    if not isinstance(e,CurrentEvidence):e=CurrentEvidence()
    fin=e.financials or {}
    # Annual trends alone do not verify current balance sheet/cash/debt or new events.
    annual=bool(fin.get('as_of') and recent(fin['as_of'],as_of) and fin.get('fresh') is True and fin.get('evidence_valid') is True and
                all(fin.get(k) is not None for k in ('revenue_growing','eps_growing','cashflow_positive','eps_latest_positive','cashflow_latest_positive')))
    balance=bool(e.review_reference and e.debt_review_pass and recent(e.balance_sheet_review_as_of,as_of))
    price=bool(positive(e.current_price) and recent(e.price_as_of,as_of) and e.price_source.startswith('https://') and e.review_reference)
    changes=bool(e.review_reference and e.changes_review_start and e.changes_review_start<=first and recent(e.changes_review_as_of,as_of))
    return dict(annual_fundamentals_verified=annual,current_financials_verified=annual and balance,
                balance_sheet_debt_verified=balance,current_price_verified=price,
                current_valuation_verified=bool(valuation_valid(e.valuation,as_of) and price and e.valuation.as_of==e.price_as_of),post_purchase_changes_verified=changes)


def build(events,as_of,evidence=None,months=6):
    """Pure backend selection. Explicit fixtures may supply typed evidence in tests.

    Production constructs CurrentEvidence from SEC summaries only; no licensed price
    provider is yet approved. Therefore missing market evidence cannot pass selection.
    """
    evidence=evidence or {};first=months_before(date.fromisoformat(as_of),months).isoformat()
    rows=[dict(x) for x in events if first<=x.get('transaction_date','')<=as_of and x.get('filed','9999')<=as_of]
    suspend_security_aliases(rows)
    by_cik=defaultdict(list)
    for x in rows:by_cik[x['cik']].append(x)
    grouped=defaultdict(list)
    for w in issuer_windows(rows,as_of,months):grouped[w['cik']].append(w)
    stats=Counter(companies_with_purchase_rows=len(by_cik),purchase_rows=len(rows))
    for k in ('companies_with_eligible_equity','companies_with_unambiguous_windows','companies_weekly_base_pass',
              'companies_historical_cap_threshold_pass','companies_current_cap_pass','companies_annual_fundamentals_verified',
              'companies_current_financials_verified','companies_current_prices_verified','companies_valuation_verified',
              'companies_post_purchase_review_verified','companies_split_comparison_verified','selected_companies',
              'pending_base_candidates','companies_below_weekly_minimum','companies_without_usable_window'):stats[k]=0
    funnel=Counter({k:0 for k in ('weekly_base','historical_cap_and_threshold','current_cap','current_financials','current_price','valuation','split_comparison','post_purchase_review','homepage')})
    companies=[];details={}
    for cik,source in sorted(by_cik.items()):
        windows=grouped[cik];e=evidence.get(cik,CurrentEvidence());checks=current_checks(e,as_of,first)
        if any(x.get('purchase_eligible') is not False and not x.get('amendment') for x in source):stats['companies_with_eligible_equity']+=1
        clean=[w for w in windows if w['aggregation_verified']]
        if clean:stats['companies_with_unambiguous_windows']+=1
        else:stats['companies_without_usable_window']+=1
        base=[w for w in clean if w['amount']>=DEFAULT_FILTERS['min_weekly_amount']]
        for w in windows:
            cap=e.historical_caps.get(w['window_end']) if isinstance(e,CurrentEvidence) else None
            w['historical_market_cap']=cap.value if cap_valid(cap,w['window_end']) else None
            w['historical_market_cap_as_of']=cap.as_of if cap_valid(cap,w['window_end']) else None
            w['historical_market_cap_source']=cap.source_url if cap_valid(cap,w['window_end']) else None
            w['filters']=filter_result(w['amount'],w['historical_market_cap'])
            w['weekly_economic_verified']=w['aggregation_verified'] and w['filters']['status']=='supera'
            adjusted=e.adjusted_insider_prices.get(w['window_end']) if isinstance(e,CurrentEvidence) else None
            w['split_comparison_verified']=bool(checks['current_price_verified'] and positive(w.get('weighted_price')) and e.split_review_reference and positive(adjusted))
            w['adjusted_insider_price']=adjusted if w['split_comparison_verified'] else None
            w['distance_from_insider_pct']=round((e.current_price/adjusted-1)*100,4) if w['split_comparison_verified'] else None
        economic=[w for w in base if w['weekly_economic_verified']]
        eligible=[w for w in economic if w['split_comparison_verified']]
        cap_verified=valuation_valid(e.valuation,as_of)
        current_cap=e.valuation.market_cap if cap_verified else None
        current_cap_pass=current_cap is not None and current_cap>=DEFAULT_FILTERS['min_market_cap']
        for key,value in checks.items():
            metric={'annual_fundamentals_verified':'companies_annual_fundamentals_verified','current_financials_verified':'companies_current_financials_verified','current_price_verified':'companies_current_prices_verified','current_valuation_verified':'companies_valuation_verified','post_purchase_changes_verified':'companies_post_purchase_review_verified'}.get(key)
            if base and value and metric:stats[metric]+=1
        if current_cap_pass and base:stats['companies_current_cap_pass']+=1
        if economic:stats['companies_historical_cap_threshold_pass']+=1
        if eligible:stats['companies_split_comparison_verified']+=1
        if base:stats['companies_weekly_base_pass']+=1;funnel['weekly_base']+=1
        elif clean:stats['companies_below_weekly_minimum']+=1
        stages=[bool(base),bool(economic),current_cap_pass,checks['current_financials_verified'],checks['current_price_verified'],checks['current_valuation_verified'],bool(eligible),checks['post_purchase_changes_verified']]
        good=True
        for key,value in zip(list(funnel)[1:-1],stages[1:]):
            good=good and stages[0] and value
            if good:funnel[key]+=1
        # Pick a single best window; retain EVERY base-significant window in details.
        choices=eligible or economic or base or clean or windows
        if not choices:continue
        best=max(choices,key=lambda w:(w['amount'],w['window_end']))
        latest=max(source,key=lambda x:(x['filed'],x['id']))
        item=dict(latest,amount=best['amount'],analysis_as_of=as_of,officer=any(x.get('officer') for x in best['transactions']),director=any(x.get('director') for x in best['transactions']),officer_title=' / '.join(x.get('officer_title','') for x in best['transactions']))
        analysis=screen(item,e.financials,valuation=e.valuation)
        confirmed=bool(all(stages) and analysis['quality_pass'] and analysis['score_status']=='verificato')
        reasons=[]
        for okay,label in [(bool(base),'Nessuna finestra non ambigua raggiunge 100.000 USD dichiarati'),(bool(economic),'Capitalizzazione storica e soglia proporzionale non verificate'),(current_cap_pass,'Capitalizzazione corrente minima non verificata'),(checks['current_financials_verified'],'Bilancio, flussi e debito attuali non completamente verificati'),(checks['current_price_verified'],'Prezzo corrente verificato assente'),(checks['current_valuation_verified'],'Valutazione corrente verificata assente'),(bool(eligible),'Prezzo insider rettificato per split non verificato'),(checks['post_purchase_changes_verified'],'Cambiamenti successivi agli acquisti da verificare')]:
            if not okay:reasons.append(label)
        if not checks['current_financials_verified']:
            analysis['radar_score']=None;analysis['score_status']='non_verificabile'
        if not all(stages[4:]) and analysis['score_status']=='verificato':
            analysis['radar_score']=min(analysis['radar_score'],49);analysis['score_status']='provvisorio'
        analysis['rule_quality_pass']=analysis['quality_pass']
        analysis['quality_pass']=confirmed
        analysis['fundamentals_verified']=checks['current_financials_verified']
        analysis['warnings']=list(dict.fromkeys(analysis['warnings']+reasons))
        status='selected' if confirmed else 'excluded' if all(stages) else 'pending' if base else 'excluded'
        if confirmed:stats['selected_companies']+=1;funnel['homepage']+=1
        elif status=='pending':stats['pending_base_candidates']+=1
        # Compact company record: never ship raw transactions in homepage ranking.
        public={k:v for k,v in best.items() if k not in ('transactions','fundamentals','analysis','possible_duplicate_ids')}
        public.update(id=f'issuer:{cik}',analysis=analysis,selection_status=status,selection_reasons=reasons,
                      market_cap=current_cap,market_cap_verified=cap_verified,
                      current_price=e.current_price if checks['current_price_verified'] else None,
                      current_price_as_of=e.price_as_of if checks['current_price_verified'] else None,
                      current_valuation_as_of=e.valuation.as_of if cap_verified else None,
                      current_checks=checks,significant_window_count=len(base),search_start=first,
                      detail_url=f'./data/companies/{cik}.json',transaction_ids=[x['id'] for x in best['transactions']])
        companies.append(public)
        details[cik]=dict(company=public,as_of=as_of,search_start=first,
                          semester_windows=[{k:w.get(k) for k in ('window_start','window_end','amount','reported_amount','transaction_count','reported_transaction_count','aggregation_verified','weighted_price','historical_market_cap','historical_market_cap_as_of','weekly_economic_verified','split_comparison_verified','adjusted_insider_price','distance_from_insider_pct')} for w in windows],
                          significant_windows=[{k:v for k,v in w.items() if k not in ('transactions','fundamentals','analysis')} for w in base],
                          transactions=source,overlap_warning='Finestre sovrapposte: non sommare importi o conteggi tra finestre.',
                          currency_basis='Prezzi USD dichiarati secondo Form 4, istruzione 5; non verifica individuale del deposito',currency_source=FORM4_CURRENCY_SOURCE)
    companies.sort(key=lambda c:((c['analysis'].get('radar_score') if c['analysis'].get('radar_score') is not None else -1),c['amount']),reverse=True)
    return dict(version=2,app_version='0.8.2',as_of=as_of,search_months=months,search_start=first,window_start=first,
                aggregation_days=7,filters=DEFAULT_FILTERS,groups=[c for c in companies if c['selection_status']=='selected'],
                stats=dict(stats),funnel=dict(funnel),history_months_available=12,historical_windows=[],
                search_index_url='./data/search_index.json',pending_index_url='./data/pending_index.json',
                history_status='Semestre calcolato lato Python; dati mancanti non sono opportunità confermate',
                buy_signal=False,notify=False),companies,details
