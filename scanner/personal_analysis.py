"""Join own-token market cache with SEC detail and explicit security/class reviews.

Private outputs remain in .private-market. This cannot promote public Pages cards.
Run: python -m scanner.personal_analysis --cik 1031203 --tolerance 15
"""
import argparse,json
from pathlib import Path
from scanner.market_math import near_insider,capitalization,day,number
from scanner.personal_market import CACHE,ROOT,private_path,load,save,PersonalDataError
from scanner.radar import filter_result


def analyze_company(detail,reviews,caches,as_of,tolerance=15):
    if not number(tolerance) or not 0<=tolerance<=100:raise ValueError('Invalid tolerance')
    cik=detail['company']['cik']
    results=[];mapping=reviews.get('security_titles',{})
    if reviews.get('cik')!=cik:raise ValueError('Review CIK mismatch')
    securities=reviews.get('securities',{})
    def normalized(security_id):
        identity=securities.get(security_id,{})
        cache=caches.get(identity.get('symbol'),{})
        if (not identity.get('class_review_reference') or identity.get('currency')!='USD' or not identity.get('identity_source_url','').startswith('https://www.sec.gov/Archives/')
            or cache.get('license_scope')!='personal_internal_only' or cache.get('redistribution_allowed') is not False
            or cache.get('metadata',{}).get('ticker','').upper()!=identity.get('symbol') or cache.get('metadata',{}).get('exchangeCode')!=identity.get('exchange')
            or not day(identity.get('valid_from')) or not day(identity.get('valid_to')) or not identity['valid_from']<=detail['search_start']<=as_of<=identity['valid_to']):return []
        return [dict(day=r['date'][:10],close=r['close'],split_factor=r['splitFactor'],security_id=security_id,currency='USD',exchange=identity['exchange']) for r in cache.get('prices',[])]
    prices={sid:normalized(sid) for sid in securities}
    def cap_at(target):
        classes=[]
        for sid,identity in securities.items():
            ps=[r for r in prices[sid] if r['day']==target]
            ss=[r for r in identity.get('outstanding_shares',[]) if r.get('end')==target and r.get('filed','9999')<as_of]
            # Conflicting observations cannot silently choose the largest share count.
            if len(ps)!=1 or len(ss)!=1:return None
            classes.append(dict(security_id=sid,class_review_reference=identity.get('class_review_reference'),price=ps[0],shares=ss[0]))
        return capitalization(classes,target,as_of,all_classes_review_reference=reviews.get('all_equity_classes_review_reference'))['value']
    for window in detail.get('significant_windows',[]):
        tx=[t for t in detail.get('transactions',[]) if t.get('purchase_eligible') and not t.get('amendment') and window['window_start']<=t['transaction_date']<=window['window_end']]
        ids={mapping.get(t.get('security_title')) for t in tx}
        sid=next(iter(ids)) if len(ids)==1 and None not in ids else None
        rows=prices.get(sid,[]);identity=securities.get(sid,{})
        tx=[dict(t,security_id=sid) for t in tx]
        comparison=near_insider(tx,rows,as_of,security_id=sid,actions_reviewed=bool(identity.get('corporate_actions_review_reference')),tolerance_pct=tolerance)
        latest=comparison.get('price_as_of');hc=cap_at(window['window_end']);cc=cap_at(latest) if latest else None
        economic=filter_result(window['amount'],hc)
        results.append(dict(window_start=window['window_start'],window_end=window['window_end'],comparison=comparison,
                            historical_market_cap=hc,current_market_cap=cc,historical_filters=economic,
                            current_cap_pass=cc is not None and cc>=500_000_000,
                            current_valuation_verified=False,fully_verified_opportunity=False))
    return dict(cik=cik,as_of=as_of,scope='personal_internal_only',redistribution_allowed=False,windows=results,
                near_price_count=sum(w['comparison']['within_band'] is True for w in results),
                note='Price proximity is not a financial qualification. Debt, sector valuation and post-purchase review remain required.',
                buy_signal=False,notify=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cik',type=int,required=True);p.add_argument('--tolerance',type=float,default=15)
    a=p.parse_args();private_path()
    detail=load(ROOT/f'docs/data/companies/{a.cik}.json',{})
    reviews=load(CACHE/f'reviews/{a.cik}.json',{})
    if not detail or not reviews:raise SystemExit('Need SEC detail and private class review; see research/personal-market.md')
    caches={s['symbol']:load(CACHE/(s['symbol']+'.json'),{}) for s in reviews['securities'].values()}
    result=analyze_company(detail,reviews,caches,detail['as_of'],a.tolerance)
    folder=CACHE/'analysis';folder.mkdir(exist_ok=True,mode=0o700);save(folder/f'{a.cik}.json',result)
    print(json.dumps(dict(status='private_analysis_saved',windows=len(result['windows']),public_export=False)))

if __name__=='__main__':main()
