import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scanner.preliminary import rank, shares_observations, recent_filings
from scanner.universe import refresh_financials
from scanner.financial_review import review


class PreliminaryTests(unittest.TestCase):
    def test_missing_financials_visible_without_complete_rating_and_selected_removed(self):
        cs=[dict(cik=i,selection_status='pending',amount=amount,aggregation_verified=True,analysis={'radar_score':99,'insider_strength_score':50}) for i,amount in [(1,200000),(2,500000),(3,99000)]]
        cs.append(dict(cs[0],cik=4,selection_status='selected'))
        rs={c['cik']:review(None,'2026-10-25') for c in cs}
        rows=rank(cs,rs)
        self.assertEqual([c['cik'] for c in rows],[2,1])
        self.assertTrue(all(c['analysis']['radar_score'] is None for c in rows))
        self.assertTrue(all(c['analysis']['quality_pass'] is False for c in rows))
        cs[0]['selection_status']='selected'
        self.assertEqual([c['cik'] for c in rank(cs,rs)],[2])

    def test_extreme_amount_preserved_but_not_ranked_as_strongest(self):
        cs=[dict(cik=i,selection_status='pending',amount=a,aggregation_verified=True) for i,a in [(1,23e9),(2,200000)]]
        rs={c['cik']:review(None,'2026-10-25') for c in cs}
        rows=rank(cs,rs)
        self.assertEqual([r['cik'] for r in rows],[2,1])
        self.assertEqual(rows[1]['amount'],23e9)
        self.assertTrue(rows[1]['amount_review_required'])

    def test_ambiguous_aggregation_not_promoted(self):
        c=dict(cik=1,selection_status='pending',amount=1000000,aggregation_verified=False)
        self.assertEqual(rank([c],{}),[])

    def test_shares_are_dated_not_class_certified(self):
        r=dict(val=100,end='2026-06-30',filed='2026-07-30',form='10-Q')
        raw={'facts':{'dei':{'EntityCommonStockSharesOutstanding':{'units':{'shares':[r,dict(r,val=999,filed='2026-10-26'),dict(r,val=float('nan'))]}}}}}
        result=shares_observations(raw,'2026-10-25')
        self.assertEqual(result[0]['val'],100)
        self.assertFalse(result[0]['class_scope_verified'])

    def test_corporate_index_excludes_future_and_never_certifies_changes(self):
        raw={'cik':'1','filings':{'recent':{'form':['8-K','10-Q','8-K'],'filingDate':['2026-06-01','2026-04-01','2026-10-26'],'accessionNumber':['0000000001-26-000001']*3}}}
        result=recent_filings(raw,'2026-05-01','2026-10-25')
        self.assertEqual(len(result['filings']),1)
        self.assertFalse(result['substantive_review_verified'])

    def test_failed_company_backoff_preserves_cache_and_advances_queue(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);p=root/'data/analysis/1.json';p.parent.mkdir(parents=True)
            old={'cik':1,'attempted_on':'2026-10-25','error':'HTTPError','financials':{'revenue_growing':True}}
            p.write_text(json.dumps(old))
            cs=[dict(cik=i,selection_status='pending',amount=1000000,window_start='2026-05-01') for i in [1,2]]
            with patch('scanner.sec.get',side_effect=RuntimeError('test failure')) as get:
                result=refresh_financials(root,cs,'2026-10-25',1)
            self.assertEqual(result['failed'],1)
            self.assertIn('0000000002',get.call_args[0][0])
            self.assertEqual(json.loads(p.read_text()),old)
            with patch('scanner.sec.get',side_effect=AssertionError('Backoff')) as get:
                refresh_financials(root,cs,'2026-10-25',2)
                get.assert_not_called()
