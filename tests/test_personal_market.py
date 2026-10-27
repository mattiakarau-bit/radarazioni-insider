import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime,timezone
from scanner.personal_market import TiingoPersonal,PersonalDataError,private_path

TOKEN='synthetic_test_token_not_a_credential'
NOW=datetime(2026,10,27,tzinfo=timezone.utc)

class PersonalMarketTests(unittest.TestCase):
    def run_client(self,tmp,transport):
        return patch('scanner.personal_market.CACHE',Path(tmp)/'.private-market')

    def test_ci_cannot_download_personal_prices(self):
        with patch.dict(os.environ,{'GITHUB_ACTIONS':'true'}):
            with self.assertRaises(PersonalDataError):private_path()

    def test_own_token_header_only_private_cache_and_same_day_reuse(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{},clear=True),self.run_client(tmp,None):
            calls=[]
            def transport(url,headers):
                calls.append(url);self.assertNotIn(TOKEN,url);self.assertEqual(headers['Authorization'],'Token '+TOKEN)
                return json.dumps({'ticker':'GPI','exchangeCode':'NYSE'} if '?' not in url else [{'date':'2026-10-26T00:00:00Z','close':10,'splitFactor':1}]).encode()
            c=TiingoPersonal(TOKEN,transport=transport,now=NOW);r=c.fetch('GPI','2026-05-01','2026-10-26')
            self.assertFalse(r['redistribution_allowed']);self.assertFalse(r['identity_class_currency_verified'])
            c.fetch('GPI','2026-05-01','2026-10-26');self.assertEqual(len(calls),2)
            self.assertNotIn(TOKEN,(Path(tmp)/'.private-market/GPI.json').read_text())

    def test_invalid_prices_do_not_replace_cache(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{},clear=True),self.run_client(tmp,None):
            c=TiingoPersonal(TOKEN,transport=lambda u,h:json.dumps({'ticker':'GPI','exchangeCode':'NYSE'} if '?' not in u else [{'date':'2027-01-01','close':10,'splitFactor':1}]).encode(),now=NOW)
            with self.assertRaises(PersonalDataError):c.fetch('GPI','2026-05-01','2026-10-26')
            self.assertFalse((Path(tmp)/'.private-market/GPI.json').exists())

    def test_free_monthly_symbol_limit_and_request_limit(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{},clear=True),self.run_client(tmp,None):
            c=TiingoPersonal(TOKEN,transport=lambda *a:(_ for _ in ()).throw(AssertionError('No network')),now=NOW)
            c.ledger['symbols']=[str(i) for i in range(500)]
            with self.assertRaises(PersonalDataError):c.request('GPI','')
            c.ledger['symbols']=[];c.calls=20
            with self.assertRaises(PersonalDataError):c.request('GPI','')

    def test_no_export_location_or_future_request(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{},clear=True),self.run_client(tmp,None):
            with self.assertRaises(PersonalDataError):private_path(Path(tmp)/'docs/data')
            c=TiingoPersonal(TOKEN,transport=lambda *a:None,now=NOW)
            with self.assertRaises(PersonalDataError):c.fetch('GPI','2026-10-28')
