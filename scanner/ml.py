"""Real-data research pipeline. No training/metrics without verified forward targets."""
from __future__ import annotations
import argparse, hashlib, json, math, sqlite3
from collections import Counter, defaultdict
from datetime import date, timedelta, datetime, timezone
from pathlib import Path
from scanner.run import save_json
from scanner.bulk import iter_events

FEATURES=('log_purchase_amount','log_shares','officer','director','ten_pct','filing_delay_days')
SCHEMA='''
CREATE TABLE IF NOT EXISTS providers(provider_id TEXT PRIMARY KEY,url_prefix TEXT,license_url TEXT,redistribution_approved INTEGER,reviewed_at TEXT);
CREATE TABLE IF NOT EXISTS events(event_id TEXT PRIMARY KEY, issuer_cik INTEGER NOT NULL,security_id TEXT,
 filed TEXT NOT NULL,available_from TEXT NOT NULL,transaction_date TEXT NOT NULL,raw_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS identities(security_id TEXT,ticker TEXT,valid_from TEXT,valid_to TEXT,source_url TEXT,observed_at TEXT,
 PRIMARY KEY(security_id,ticker,valid_from));
CREATE TABLE IF NOT EXISTS prices(security_id TEXT,day TEXT,total_return_index REAL,adjustments_verified INTEGER,
 delisting_settlement_verified INTEGER,source_url TEXT,published_at TEXT,license_approved INTEGER,
 PRIMARY KEY(security_id,day));
CREATE TABLE IF NOT EXISTS corporate_actions(security_id TEXT,day TEXT,kind TEXT,value REAL,published_at TEXT,source_url TEXT,
 PRIMARY KEY(security_id,day,kind));
CREATE TABLE IF NOT EXISTS financial_facts(issuer_cik INTEGER,concept TEXT,period_end TEXT,public_at TEXT,value REAL,source_url TEXT,
 PRIMARY KEY(issuer_cik,concept,period_end,public_at));
CREATE TABLE IF NOT EXISTS features(event_id TEXT PRIMARY KEY,as_of TEXT,feature_version TEXT,values_json TEXT,rule_score REAL,
 max_source_public_at TEXT,source_kind TEXT);
CREATE TABLE IF NOT EXISTS targets(event_id TEXT,horizon INTEGER,entry_day TEXT,exit_day TEXT,excess_return REAL,label INTEGER,
 status TEXT,benchmark TEXT,cost_bps REAL,source_digest TEXT,PRIMARY KEY(event_id,horizon));
'''


def connect(path):
    db=sqlite3.connect(path);db.row_factory=sqlite3.Row;db.executescript(SCHEMA);return db


def point_in_time_features(event):
    """Only as-filed fields, never current listing, later amendments, or future fundamentals."""
    if event.get('amendment') or not event.get('purchase_eligible'):return None
    try:
        delay=(date.fromisoformat(event['filed'])-date.fromisoformat(event['transaction_date'])).days
        if delay<0 or event.get('amount',0)<=0 or event.get('shares',0)<=0:return None
        return dict(log_purchase_amount=math.log1p(event['amount']),log_shares=math.log1p(event['shares']),
                    officer=int(event['officer']),director=int(event['director']),ten_pct=int(event['ten_pct']),filing_delay_days=delay)
    except (ValueError,TypeError,KeyError):return None


def eligible_feature_ids(events):
    # De-duplicate decisions using ONLY co-reports/amendments already filed by the
    # event's filing day. Later annotations never erase earlier information sets.
    economic=defaultdict(dict);amendments=defaultdict(list)
    def key(e):return (e['cik'],e['transaction_date'],e['security_title'].casefold(),e['shares'],e['unit_price'])
    for e in events:
        economic[key(e)][e['accession']]=e['filed']
        if e['amendment']:
            for owner in e['owner_ciks']:amendments[(e['cik'],owner,e['period_of_report'])].append(e['filed'])
    result=set()
    for e in events:
        if sum(d<=e['filed'] for d in economic[key(e)].values())>1:continue
        if any(d<=e['filed'] for owner in e['owner_ciks'] for d in amendments[(e['cik'],owner,e['period_of_report'])]):continue
        if point_in_time_features(e) is not None:result.add(e['id'])
    return result


def select_public_facts(rows,as_of):
    return [r for r in rows if r['public_at']<=as_of and r['period_end']<=as_of]


def make_target(prices,benchmark,available_from,horizon,cost_bps=20):
    """30/90/180 calendar-day horizons, first common session after availability.

    TRI must already incorporate verified splits, dividends and delisting proceeds.
    No forward fill, zero-return substitution or ticker-based identity inference.
    """
    if horizon not in (30,90,180):raise ValueError('Unsupported horizon')
    if not isinstance(cost_bps,(int,float)) or not math.isfinite(cost_bps) or cost_bps<0:raise ValueError('Invalid cost assumption')
    observed_through=date.today().isoformat()
    missing=dict(status='missing_verified_prices',label=None,excess_return=None)
    def usable(rows):
        return {r['day']:r for r in rows if r['day']<=observed_through and r.get('adjustments_verified') and r.get('license_approved') and r.get('source_url') and
                isinstance(r.get('total_return_index'),(int,float)) and math.isfinite(r['total_return_index']) and r['total_return_index']>0}
    p,b=usable(prices),usable(benchmark);common=sorted(set(p)&set(b));entry=next((d for d in common if d>=available_from),None)
    if not entry or (date.fromisoformat(entry)-date.fromisoformat(available_from)).days>7:return missing
    due=(date.fromisoformat(entry)+timedelta(days=horizon)).isoformat();exit_day=next((d for d in common if d>=due),None)
    # Refuse silently jumping over a long data gap, suspension or unresolved delisting.
    if not exit_day or (date.fromisoformat(exit_day)-date.fromisoformat(due)).days>7:return missing
    for rows in (prices,benchmark):
        if any(r.get('kind')=='delisted' and entry<=r['day']<=exit_day and not r.get('delisting_settlement_verified') for r in rows):
            return dict(status='missing_delisting_settlement',label=None,excess_return=None)
    stock=p[exit_day]['total_return_index']/p[entry]['total_return_index']-1-cost_bps/10000
    bench=b[exit_day]['total_return_index']/b[entry]['total_return_index']-1
    excess=stock-bench
    provenance=[p[entry],p[exit_day],b[entry],b[exit_day]]
    return dict(status='verified',label=int(excess>0),excess_return=excess,entry_day=entry,exit_day=exit_day,
                source_digest=hashlib.sha256(json.dumps(provenance,sort_keys=True).encode()).hexdigest())


def chronological_split(rows,embargo_days=7):
    """Purged train/validation/test. Every label ends strictly before next block."""
    rows=sorted(rows,key=lambda r:r['as_of']);n=len(rows)
    if n<10:return [],[],[]
    a,b=rows[int(n*.6)]['as_of'],rows[int(n*.8)]['as_of']
    def before(exit_day,boundary):return (date.fromisoformat(exit_day)+timedelta(days=embargo_days)).isoformat()<boundary
    train=[r for r in rows if r['as_of']<a and before(r['exit_day'],a)]
    validation=[r for r in rows if a<=r['as_of']<b and before(r['exit_day'],b)]
    test=[r for r in rows if r['as_of']>=b]
    return train,validation,test


def sufficient(rows):
    if len(rows)<500:return False,'Fewer than 500 verified event targets'
    if len({r['issuer_cik'] for r in rows})<100:return False,'Fewer than 100 issuers'
    if (date.fromisoformat(max(r['as_of'] for r in rows))-date.fromisoformat(min(r['as_of'] for r in rows))).days<3*365:return False,'Less than three years'
    blocks=chronological_split(rows)
    if any(len(block)<50 or min(Counter(r['label'] for r in block).values(),default=0)<20 or len({r['label'] for r in block})<2 for block in blocks):
        return False,'Insufficient purged chronological blocks/classes'
    return True,None


def train_models(rows):
    okay,reason=sufficient(rows)
    if not okay:return dict(trained=False,status='blocked',reason=reason,metrics=None)
    if any(r.get('source_kind')!='SEC_real_verified_target' or r['max_source_public_at']>r['as_of'] for r in rows):
        return dict(trained=False,status='blocked',reason='Unverified provenance or future feature data',metrics=None)
    import numpy as np
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.metrics import roc_auc_score,average_precision_score,brier_score_loss,accuracy_score
    train,val,test=chronological_split(rows)
    def matrix(block):return np.array([[r['features'][k] for k in FEATURES] for r in block],dtype=float)
    X,y=matrix(train),np.array([r['label'] for r in train]);VX,VY=matrix(val),np.array([r['label'] for r in val]);TX,TY=matrix(test),np.array([r['label'] for r in test])
    candidates={'logistic_regression':make_pipeline(StandardScaler(),LogisticRegression(max_iter=2000,random_state=17)),
                'gradient_boosting':GradientBoostingClassifier(n_estimators=100,max_depth=2,learning_rate=.05,random_state=17)}
    fitted={};validation={}
    for name,model in candidates.items():
        model.fit(X,y);fitted[name]=model;validation[name]=float(brier_score_loss(VY,model.predict_proba(VX)[:,1]))
    chosen=min(validation,key=validation.get) # Choose on validation, never the test.
    metrics={};rng=np.random.default_rng(17)
    for name,model in fitted.items():
        probabilities=model.predict_proba(TX)[:,1]
        # Cluster bootstrap by issuer, not iid overlapping event rows.
        groups=defaultdict(list)
        for i,r in enumerate(test):groups[r['issuer_cik']].append(i)
        keys=list(groups);aucs=[]
        for _ in range(200):
            idx=[i for k in rng.choice(keys,len(keys),replace=True) for i in groups[k]]
            if len(set(TY[idx]))==2:aucs.append(roc_auc_score(TY[idx],probabilities[idx]))
        metrics[name]=dict(roc_auc=float(roc_auc_score(TY,probabilities)),average_precision=float(average_precision_score(TY,probabilities)),
                           brier=float(brier_score_loss(TY,probabilities)),accuracy=float(accuracy_score(TY,probabilities>=.5)),
                           roc_auc_95_cluster_bootstrap=[float(x) for x in np.quantile(aucs,[.025,.975])] if aucs else None)
        estimator=model[-1] if name=='logistic_regression' else model
        metrics[name]['feature_effects']=dict(zip(FEATURES,[float(x) for x in (estimator.coef_[0] if name=='logistic_regression' else estimator.feature_importances_)]))
    baseline=np.repeat(y.mean(),len(TY))
    rule_rows=[r for r in test if r.get('rule_score') is not None]
    rule_auc=roc_auc_score([r['label'] for r in rule_rows],[r['rule_score'] for r in rule_rows]) if len({r['label'] for r in rule_rows})==2 else None
    return dict(trained=True,status='research_only_not_deployed',chosen_on_validation=chosen,validation_brier=validation,metrics=metrics,
                benchmark='verified total-return benchmark; target is net excess return > 0',
                constant_baseline_brier=float(brier_score_loss(TY,baseline)),rules_baseline_auc=float(rule_auc) if rule_auc is not None else None,
                rules_baseline_status='available' if rule_auc is not None else 'missing_point_in_time_rule_scores',
                split_counts=dict(train=len(train),validation=len(val),test=len(test)),uncertainty='issuer-cluster bootstrap; not a guarantee',
                buy_signal=False,notify=False)


def populate_targets(db,benchmark_id='BENCHMARK_TOTAL_RETURN',cost_bps=20):
    approved=[dict(r) for r in db.execute('SELECT * FROM providers WHERE redistribution_approved=1')]
    def series(security_id):
        rows=[dict(r) for r in db.execute('SELECT * FROM prices WHERE security_id=? ORDER BY day',(security_id,))]
        return [r for r in rows if any(p['url_prefix'].startswith('https://') and p['license_url'] and p['reviewed_at'] and r['source_url'].startswith(p['url_prefix']) for p in approved)]
    benchmark=series(benchmark_id)
    rows=db.execute('SELECT e.*,f.as_of FROM events e JOIN features f USING(event_id)').fetchall()
    for row in rows:
        prices=series(row['security_id']) if row['security_id'] else []
        for h in (30,90,180):
            target=make_target(prices,benchmark,row['available_from'],h,cost_bps)
            db.execute('INSERT OR REPLACE INTO targets VALUES(?,?,?,?,?,?,?,?,?,?)',
                       (row['event_id'],h,target.get('entry_day'),target.get('exit_day'),target.get('excess_return'),target.get('label'),target['status'],benchmark_id,cost_bps,target.get('source_digest')))
    db.commit()


def training_rows(db,horizon):
    rows=db.execute("SELECT e.issuer_cik,f.*,t.exit_day,t.label,t.source_digest FROM features f JOIN events e USING(event_id) JOIN targets t USING(event_id) WHERE t.horizon=? AND t.status='verified' AND t.label IS NOT NULL",(horizon,)).fetchall()
    return [dict(event_id=r['event_id'],issuer_cik=r['issuer_cik'],as_of=r['as_of'],exit_day=r['exit_day'],label=r['label'],
                 source_kind='SEC_real_verified_target' if r['source_kind']=='SEC_real' and r['source_digest'] else 'unverified',
                 max_source_public_at=r['max_source_public_at'],features=json.loads(r['values_json']),rule_score=r['rule_score']) for r in rows]


def research_status(root,db_path):
    db=connect(db_path);count=0;feature_count=0
    events=list(iter_events(root));feature_ids=eligible_feature_ids(events)
    db.execute('DELETE FROM features');db.execute('DELETE FROM targets')
    for e in events:
        count+=1
        previous=db.execute('SELECT security_id FROM events WHERE event_id=?',(e['id'],)).fetchone()
        security_id=previous['security_id'] if previous else None
        db.execute('INSERT OR REPLACE INTO events VALUES(?,?,?,?,?,?,?)',(e['id'],e['cik'],security_id,e['filed'],e['available_from'],e['transaction_date'],json.dumps(e)))
        values=point_in_time_features(e)
        if values and e['id'] in feature_ids:
            feature_count+=1
            db.execute('INSERT OR REPLACE INTO features VALUES(?,?,?,?,?,?,?)',(e['id'],e['available_from'],'as_filed_v1',json.dumps(values),None,e['filed'],'SEC_real'))
    db.commit();populate_targets(db)
    horizon_models={str(h):train_models(training_rows(db,h)) for h in (30,90,180)}
    verified={str(h):len(training_rows(db,h)) for h in (30,90,180)}
    trained=any(r['trained'] for r in horizon_models.values())
    status=dict(version=1,updated_utc=datetime.now(timezone.utc).isoformat(timespec='seconds'),events_stored=count,
                point_in_time_feature_rows=feature_count,verified_targets=verified,trained=trained,status='research_only' if trained else 'blocked',
                models_prepared=['logistic_regression','gradient_boosting'],horizons=horizon_models,
                metrics={h:r.get('metrics') for h,r in horizon_models.items()} if trained else None,benchmark_returns=None,
                missing=['licensed_verified_total_return_prices','historical_security_identity','splits_dividends_delisting_proceeds','point_in_time_rule_baseline'] if not trained else [],
                min_verified_targets=500,min_issuers=100,min_years=3,buy_signal=False,notify=False,
                note='Nessuna performance o etichetta inventata; database ricostruibile dagli shard SEC. Adapter prezzi/identità non ancora approvati.')
    status['verified_source_events_in_current_import']=count
    status['events_stored']=db.execute('SELECT COUNT(*) FROM events').fetchone()[0]
    db.close();save_json(root/'docs/data/ml_status.json',status);return status


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--db',type=Path)
    a=p.parse_args();db_path=a.db or a.root/'data/cache/research.sqlite';db_path.parent.mkdir(parents=True,exist_ok=True)
    print(json.dumps(research_status(a.root,db_path)))

if __name__=='__main__':main()
