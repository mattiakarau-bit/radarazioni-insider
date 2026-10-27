"""Tiingo own-token/internal-use adapter. NEVER used by public Pages/Actions.

Run locally: python -m scanner.personal_market --symbol GPI --start 2026-04-27
Token comes from the local environment or hidden prompt, never a command argument.
"""
import argparse
import getpass
import json
import os
import re
import urllib.request
import urllib.error
from datetime import date,datetime,timezone,timedelta
from pathlib import Path
from scanner.market_math import day,number

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'.private-market'
TERMS='https://www.tiingo.com/documentation/appendix/developers'


class PersonalDataError(RuntimeError):pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise PersonalDataError('Unexpected redirect; token not forwarded')


def private_path(cache=None):
    cache=Path(CACHE if cache is None else cache)
    # Deliberately fixed location: no CLI output/export into Pages or tracked source.
    if cache!=CACHE or cache.is_symlink() or (cache.exists() and cache.resolve()!=cache.absolute()):
        raise PersonalDataError('Private cache must be the repository .private-market directory')
    if os.getenv('GITHUB_ACTIONS') or os.getenv('CI'):raise PersonalDataError('Personal market data disabled in CI/public workflows')
    cache.mkdir(parents=True,exist_ok=True,mode=0o700)
    return cache


def load(path,default):return json.loads(path.read_text()) if path.exists() else default


def save(path,value):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,allow_nan=False,separators=(',',':')))
    tmp.chmod(0o600);tmp.replace(path)


class TiingoPersonal:
    def __init__(self,token,*,transport=None,now=None):
        if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,128}',token):raise PersonalDataError('A personal Tiingo API token is required; never send it in chat')
        self.token=token;self.cache=private_path();self.transport=transport or self._http
        self.now=now or datetime.now(timezone.utc);self.calls=0
        self.ledger=load(self.cache/'usage.json',{})
        self.month=self.now.strftime('%Y-%m');self.hour=self.now.strftime('%Y-%m-%dT%H');self.today=self.now.date().isoformat()
        if self.ledger.get('month')!=self.month:self.ledger=dict(month=self.month,symbols=[],requests={},bytes=0)

    def _http(self,url,headers):
        try:
            with urllib.request.build_opener(NoRedirect()).open(urllib.request.Request(url,headers=headers),timeout=25) as r:
                body=r.read(8_000_001)
            if len(body)>8_000_000:raise PersonalDataError('Response too large; cache unchanged')
            return body
        except urllib.error.HTTPError as exc:
            # Never echo the request/Authorization/token or auto-upgrade/retry on 429.
            raise PersonalDataError(f'Tiingo HTTP {exc.code}; stop, check own plan/token/limits') from None
        except (urllib.error.URLError,TimeoutError):raise PersonalDataError('Tiingo network error; cache unchanged') from None

    def request(self,symbol,suffix):
        if not re.fullmatch(r'[A-Z][A-Z0-9-]{0,14}',symbol):raise PersonalDataError('Invalid provider symbol; explicit class mapping required')
        usage=self.ledger.setdefault('requests',{})
        if self.calls>=20 or usage.get(self.hour,0)>=50 or sum(v for k,v in usage.items() if k.startswith(self.today))>=1000:
            raise PersonalDataError('Personal free request budget reached')
        if symbol not in self.ledger['symbols'] and len(self.ledger['symbols'])>=500:raise PersonalDataError('500-symbol monthly free limit reached')
        if self.ledger['bytes']>=990_000_000:raise PersonalDataError('Personal bandwidth budget reached')
        if symbol not in self.ledger['symbols']:self.ledger['symbols'].append(symbol)
        usage[self.hour]=usage.get(self.hour,0)+1;self.calls+=1;save(self.cache/'usage.json',self.ledger)
        body=self.transport('https://api.tiingo.com/tiingo/daily/'+symbol+suffix,
                            {'Authorization':'Token '+self.token,'Accept':'application/json'})
        self.ledger['bytes']+=len(body);save(self.cache/'usage.json',self.ledger)
        try:return json.loads(body)
        except (ValueError,TypeError):raise PersonalDataError('Invalid Tiingo JSON; cache unchanged') from None

    def fetch(self,symbol,start,end=None):
        end=end or self.today
        if not day(start) or not day(end) or start>end or end>self.today:raise PersonalDataError('Invalid/future date range')
        path=self.cache/(symbol+'.json');old=load(path,{})
        if old.get('fetched_on')==self.today and old.get('requested_start','9999')<=start and old.get('requested_end','')>=end:return old
        metadata=old.get('metadata')
        if not metadata or (day(self.today)-day(old['fetched_on'])).days>=7:
            metadata=self.request(symbol,'')
        if not isinstance(metadata,dict) or metadata.get('ticker','').upper()!=symbol or not metadata.get('exchangeCode'):
            raise PersonalDataError('Provider identity/exchange missing; cache unchanged')
        first=start
        if old.get('requested_start','9999')<=start and old.get('prices'):
            first=max(start,(day(old['prices'][-1]['date'][:10])-timedelta(days=7)).isoformat())
        rows=self.request(symbol,f'/prices?startDate={first}&endDate={end}&resampleFreq=daily')
        if not isinstance(rows,list) or not rows:raise PersonalDataError('No prices returned; cache unchanged')
        for r in rows:
            if not isinstance(r,dict) or not day(str(r.get('date',''))[:10]) or not first<=r['date'][:10]<=end or not number(r.get('close')) or r['close']<=0 or not number(r.get('splitFactor')) or r['splitFactor']<=0:
                raise PersonalDataError('Invalid price/split row; cache unchanged')
        if len({r['date'][:10] for r in rows})!=len(rows):raise PersonalDataError('Duplicate price dates')
        merged={r['date'][:10]:r for r in old.get('prices',[]) if r['date'][:10]<first}
        merged.update({r['date'][:10]:r for r in rows})
        result=dict(provider='Tiingo',license_scope='personal_internal_only',redistribution_allowed=False,
                    terms_url=TERMS,fetched_on=self.today,requested_start=min(start,old.get('requested_start',start)),requested_end=end,
                    metadata=metadata,prices=[merged[k] for k in sorted(merged)],
                    identity_class_currency_verified=False,capitalization_verified=False,
                    note='Provider ticker is not a verified CIK/class mapping; SEC share count and corporate-action review still required')
        save(path,result);return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--symbol',required=True);p.add_argument('--start',required=True);p.add_argument('--end')
    args=p.parse_args()
    try:
        private_path()
        token=os.getenv('TIINGO_API_TOKEN') or getpass.getpass('Tiingo token personale (non salvato): ')
        result=TiingoPersonal(token).fetch(args.symbol,args.start,args.end)
        # Counts only; no restricted values in terminal logs or public reports.
        print(json.dumps(dict(status='personal_cache_saved',observations=len(result['prices']),redistribution_allowed=False)))
    except (PersonalDataError,EOFError,KeyboardInterrupt) as exc:
        raise SystemExit(str(exc) if isinstance(exc,PersonalDataError) else 'Cancelled; no account created')

if __name__=='__main__':main()
