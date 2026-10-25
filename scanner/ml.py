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


def select_public_facts(rows,as_of):
    return [r for r in rows if r['public_at']<=as_of and r['period_end']<=as_of]


def make_target(prices,benchmark,available_from,horizon,cost_bps=20):
    """30/90/180 calendar-day horizons, first common session after availability.

    TRI must already incorporate verified splits, dividends and delisting proceeds.
    No forward fill, zero-return substitution or ticker-based identity inference.
    """
    if horizon not in (30,90,180):raise ValueError('Unsupported horizon')
    missing=dict(status='missing_verified_prices',label=None,excess_return=None)
    def usable(rows):
        return {r['day']:r for r in rows if r.get('adjustments_verified') and r.get('license_approved') and r.get('source_url') and
                isinstance(r.get('total_return_index'),(int,float)) and math.isfinite(r['total_return_index']) and r['total_return_index']>0}
    p,b=usable(prices),usable(benchmark);common=sorted(set(p)&set(b));entry=next((d for d in common if d>=available_from),None)
    if not entry:return missing
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


def research_status(root,db_path):
    db=connect(db_path);count=0;feature_count=0
    for e in iter_events(root):
        count+=1
        # Stable security identity is deliberately unset until class/ticker changes are resolved.
        db.execute('INSERT OR REPLACE INTO events VALUES(?,?,?,?,?,?,?)',(e['id'],e['cik'],None,e['filed'],e['available_from'],e['transaction_date'],json.dumps(e)))
        values=point_in_time_features(e)
        if values:
            feature_count+=1
            db.execute('INSERT OR REPLACE INTO features VALUES(?,?,?,?,?,?,?)',(e['id'],e['available_from'],'as_filed_v1',json.dumps(values),None,e['filed'],'SEC_real'))
    db.commit()
    # No source registry approves price redistribution yet: even externally added prices
    # cannot silently switch on training. A reviewed provider adapter must create targets.
    status=dict(version=1,updated_utc=datetime.now(timezone.utc).isoformat(timespec='seconds'),events_stored=count,
                point_in_time_feature_rows=feature_count,verified_targets={'30':0,'90':0,'180':0},trained=False,status='blocked',
                models_prepared=['logistic_regression','gradient_boosting'],metrics=None,benchmark_returns=None,
                missing=['licensed_verified_total_return_prices','historical_security_identity','splits_dividends_delisting_proceeds','point_in_time_rule_baseline'],
                min_verified_targets=500,min_issuers=100,min_years=3,buy_signal=False,notify=False,
                note='Modelli non addestrati; nessuna performance o etichetta inventata. Database locale ricostruibile dagli shard SEC.')
    db.close();save_json(root/'docs/data/ml_status.json',status);return status


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--db',type=Path)
    a=p.parse_args();db_path=a.db or a.root/'data/cache/research.sqlite';db_path.parent.mkdir(parents=True,exist_ok=True)
    print(json.dumps(research_status(a.root,db_path)))

if __name__=='__main__':main()
