"""SEC quarterly observations, fiscal/YTD-aware and strictly point-in-time.

Never turns missing periods into zero or quarters of EPS into differences of YTD EPS.
"""
from datetime import date,timedelta
from scanner.market_math import day,number

VERSION=1
CONCEPTS={
 'revenue':(['Revenues','RevenueFromContractWithCustomerExcludingAssessedTax','RevenueFromContractWithCustomerIncludingAssessedTax','SalesRevenueNet'],'USD'),
 'net_income':(['NetIncomeLossAvailableToCommonStockholdersBasic','NetIncomeLoss'],'USD'),
 'eps':(['EarningsPerShareDiluted','EarningsPerShareBasic'],'USD/shares'),
 'operating_income':(['OperatingIncomeLoss'],'USD'),
 'operating_cashflow':(['NetCashProvidedByUsedInOperatingActivities'],'USD'),
 'capex':(['PaymentsToAcquirePropertyPlantAndEquipment'],'USD')}


def source_rows(raw,tag,unit,as_of):
    values={}
    for r in raw.get('facts',{}).get('us-gaap',{}).get(tag,{}).get('units',{}).get(unit,[]):
        start,end,filed=day(r.get('start')),day(r.get('end')),day(r.get('filed'))
        if not start or not end or not filed or filed>=day(as_of) or end>filed or not 60<=(end-start).days<=380 or not number(r.get('val')) or not r.get('accn') or r.get('form') not in ('10-Q','10-Q/A','10-K','10-K/A'):continue
        key=(r['start'],r['end'])
        if key not in values or r['filed']>values[key]['filed']:
            values[key]=dict(value=r['val'],start=r['start'],end=r['end'],filed=r['filed'],accession=r['accn'],tag=tag,unit=unit,
                             source_url=f'https://www.sec.gov/Archives/edgar/data/{int(raw["cik"])}/{r["accn"].replace("-","")}/{r["accn"]}-index.html')
    return list(values.values())


def quarters(raw,tags,unit,as_of,*,subtract_ytd=True):
    candidates=[]
    for priority,tag in enumerate(tags):
        rows=source_rows(raw,tag,unit,as_of);q={}
        for r in rows:
            span=(day(r['end'])-day(r['start'])).days
            if 60<=span<=110:q[(r['start'],r['end'])]=dict(r,derivation='reported_quarter')
            elif subtract_ytd:
                # Annual/Q3 YTD minus preceding cumulative period; fiscal start must match.
                preceding=[p for p in rows if p['start']==r['start'] and 60<=(day(r['end'])-day(p['end'])).days<=110]
                if len(preceding)!=1:continue
                prev=preceding[0];start=(day(prev['end'])+timedelta(days=1)).isoformat()
                key=(start,r['end'])
                if key not in q:q[key]=dict(r,start=start,value=r['value']-prev['value'],filed=max(r['filed'],prev['filed']),
                                             derivation='YTD_difference',inputs=[r,prev])
        seq=sorted(q.values(),key=lambda r:(r['end'],r['filed']))[-8:]
        if seq:candidates.append((seq[-1]['end'],-priority,seq))
    return max(candidates,key=lambda t:(t[0],t[1]))[2] if candidates else []


def family(sic):
    try:n=int(sic)
    except (ValueError,TypeError):return 'unknown'
    if 6300<=n<=6399:return 'insurance'
    if n==6798:return 'reit'
    if 6000<=n<=6799:return 'financial'
    return 'nonfinancial'


def analyze(raw,as_of,sic=None,revenue_scope_verified=False):
    if not day(as_of) or not isinstance(raw.get('cik'),(str,int)):raise ValueError('Invalid SEC identity/date')
    series={name:quarters(raw,tags,unit,as_of,subtract_ytd=name!='eps') for name,(tags,unit) in CONCEPTS.items()}
    if not revenue_scope_verified:series['revenue']=[]
    fcf=[]
    for r in series['operating_cashflow']:
        capex=[c for c in series['capex'] if (c['start'],c['end'])==(r['start'],r['end']) and c['value']>=0]
        if len(capex)==1:
            c=capex[0];fcf.append(dict(value=r['value']-c['value'],start=r['start'],end=r['end'],unit='USD',
                                     filed=max(r['filed'],c['filed']),derivation='CFO_minus_cash_PPE',inputs=[r,c]))
    series['free_cashflow']=fcf
    growth={}
    for name,rows in series.items():
        if not rows: growth[name]=None;continue
        latest=rows[-1]
        prev=[r for r in rows[:-1] if 350<=(day(latest['end'])-day(r['end'])).days<=380 and abs((day(latest['end'])-day(latest['start'])).days-(day(r['end'])-day(r['start'])).days)<=10]
        growth[name]=dict(pct=(latest['value']/prev[-1]['value']-1)*100,current=latest,previous=prev[-1]) if len(prev)==1 and prev[0]['value']>0 else None
    margins=[]
    if family(sic)=='nonfinancial':
        for revenue in series['revenue']:
            matches=[r for r in series['operating_income'] if (r['start'],r['end'])==(revenue['start'],revenue['end'])]
            if revenue['value']>0 and len(matches)==1:
                op=matches[0];margins.append(dict(value=op['value']/revenue['value']*100,start=revenue['start'],end=revenue['end'],filed=max(op['filed'],revenue['filed']),inputs=[op,revenue]))
    risks=[]
    for name in ('net_income','operating_cashflow','free_cashflow'):
        rows=series[name]
        if rows and rows[-1]['value']<0:risks.append('Latest quarterly '+name+' negative')
    return dict(schema=VERSION,as_of=as_of,sector_family=family(sic),sic=sic,series=series,yoy=growth,operating_margins_pct=margins,
                risks=risks,latest_period=max((r['end'] for rows in series.values() for r in rows),default=None),
                valuation_verified=False,debt_scope_verified=False,post_purchase_changes_verified=False,
                notes=['EPS uses reported quarters only; no YTD EPS subtraction','FCF is CFO minus cash PPE, matched fiscal periods',
                       'Financial/insurance/REIT sectors require separate valuation and capital review; industrial margin not applied',
                       'Observations alone do not certify investment quality; latest periods can be stale'])


def compact(report,cik):
    """Intern provenance once; avoid copying nested YTD inputs into every Pages field."""
    import hashlib,json
    facts={}
    def point(row):
        if row is None:return None
        clean={k:v for k,v in row.items() if k not in ('source_url','inputs')}
        if row.get('inputs'):clean['input_refs']=[intern(x) for x in row['inputs']]
        return clean
    def intern(row):
        clean=point(row);key=hashlib.sha256(json.dumps(clean,sort_keys=True).encode()).hexdigest()[:16]
        facts[key]=clean;return key
    series={key:[point(r) for r in rows[-4:]] for key,rows in report['series'].items()}
    growth={key:dict(pct=r['pct'],current_ref=intern(r['current']),previous_ref=intern(r['previous'])) if r else None for key,r in report['yoy'].items()}
    margins=[point(r) for r in report['operating_margins_pct'][-4:]]
    fresh=bool(report['latest_period'] and (day(report['as_of'])-day(report['latest_period'])).days<=180)
    return {**report,'cik':cik,'source_url':f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json',
            'series':series,'yoy':growth,'operating_margins_pct':margins,'source_facts':facts,
            'fresh_latest_period':fresh,'display_quarters':4,
            'provenance_note':'Referenced inputs retained once; SEC source and accession identify original filings'}
