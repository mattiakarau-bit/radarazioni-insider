import unittest
from scanner.fundamentals import summarize_company_facts, review_legacy
from scanner.scoring import screen, ValuationEvidence


def facts(values=None):
    values=values or [100,120,150]
    def series(vals):
        return [dict(start=f'{y}-01-01',end=f'{y}-12-31',filed=f'{y+1}-02-01',val=v,fp='FY',form='10-K') for y,v in zip((2023,2024,2025),vals)]
    return dict(facts={'us-gaap':{
        'Revenues':dict(units={'USD':series(values)}),
        'EarningsPerShareDiluted':dict(units={'USD/shares':series([1,2,3])}),
        'NetCashProvidedByUsedInOperatingActivities':dict(units={'USD':series([10,20,30])})}})

class FinancialEvidenceTests(unittest.TestCase):
    def test_complete_solid_favorable_fixture_can_score_high(self):
        fin=summarize_company_facts(facts(),'2026-10-24')
        val=ValuationEvidence('2026-10-24','https://fixture.example/audited',1e9,'USD',True,'test-fixture-not-real-data')
        a=screen(dict(amount=1e6,officer_title='CEO',filed='2026-10-24'),fin,valuation=val)
        self.assertEqual(a['radar_score'],94)
        self.assertEqual(a['score_status'],'verificato')
        self.assertTrue(a['quality_pass'])
        self.assertFalse(a['buy_signal']);self.assertFalse(a['notify'])
    def test_real_losses_and_cash_burn_stay_low_even_with_favorable_price(self):
        raw=facts();gaap=raw['facts']['us-gaap']
        gaap['EarningsPerShareDiluted']['units']['USD/shares'][-1]['val']=-3
        gaap['NetCashProvidedByUsedInOperatingActivities']['units']['USD'][-1]['val']=-30
        fin=summarize_company_facts(raw,'2026-10-24')
        val=ValuationEvidence('2026-10-24','https://fixture.example/source',1e9,'USD',True,'fixture-review')
        a=screen(dict(amount=1e6,officer_title='CEO',filed='2026-10-24'),fin,valuation=val)
        self.assertLessEqual(a['radar_score'],29);self.assertTrue(a['financial_problem']);self.assertFalse(a['quality_pass'])
    def test_flat_growth_is_not_a_loss(self):
        raw=facts();raw['facts']['us-gaap']['EarningsPerShareDiluted']['units']['USD/shares'][-1]['val']=1.5
        fin=summarize_company_facts(raw,'2026-10-24')
        a=screen(dict(amount=1e6,officer_title='CEO',filed='2026-10-24'),fin)
        self.assertFalse(a['financial_problem']);self.assertEqual(a['score_status'],'provvisorio')
        self.assertEqual(a['radar_score'],49)
    def test_missing_data_is_not_negative_evidence(self):
        a=screen(dict(amount=1e6),None)
        self.assertIsNone(a['radar_score']);self.assertFalse(a['financial_problem'])
    def test_untrusted_or_stale_valuation_flag_is_rejected(self):
        fin=summarize_company_facts(facts(),'2026-10-24')
        for v in [dict(verified=True,favorable=True),ValuationEvidence('2026-01-01','https://fixture.example',1e9,'USD',True,'fixture')]:
            a=screen(dict(amount=1e6,filed='2026-10-24'),fin,valuation=v)
            self.assertFalse(a['valuation_verified']);self.assertLessEqual(a['radar_score'],49)
    def test_competing_revenue_scopes_are_not_promoted(self):
        raw=facts();raw['facts']['us-gaap']['RevenueFromContractWithCustomerExcludingAssessedTax']=dict(units={'USD':[dict(x,val=x['val']/10) for x in raw['facts']['us-gaap']['Revenues']['units']['USD']]})
        fin=summarize_company_facts(raw,'2026-10-24')
        self.assertIsNone(fin['revenue_growing']);self.assertFalse(fin['evidence_valid'])
    def test_no_same_day_or_future_facts_and_no_stale_upgrade(self):
        fin=summarize_company_facts(facts(),'2026-02-01')
        self.assertEqual(fin['revenue_years'][-1]['year'],2024)
        self.assertFalse(summarize_company_facts(facts(),'2028-10-24')['fresh'])
    def test_legacy_scope_not_verified_without_source_metadata(self):
        f=review_legacy(dict(revenue_growing=True,revenue_years=[dict(year=2025,value=43.8)],eps_years=[],cashflow_years=[]))
        self.assertIsNone(f['revenue_growing']);self.assertTrue(f['legacy_indicators']['revenue_growing']);self.assertFalse(f['evidence_valid'])
