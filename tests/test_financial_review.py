import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from scanner.financial_review import review, free_cashflow, report
from scanner.fundamentals import summarize_company_facts
from tests.test_financial_evidence import facts
from tests.test_semester import verified

ASOF = '2026-10-25'
ROOT = Path(__file__).resolve().parents[1]


def snapshot():
    raw = facts()
    template = raw['facts']['us-gaap']['NetCashProvidedByUsedInOperatingActivities']
    raw['facts']['us-gaap']['PaymentsToAcquirePropertyPlantAndEquipment'] = copy.deepcopy(template)
    raw['facts']['us-gaap']['NetIncomeLossAvailableToCommonStockholdersBasic'] = copy.deepcopy(template)
    for row in raw['facts']['us-gaap']['PaymentsToAcquirePropertyPlantAndEquipment']['units']['USD']:
        row['val'] = 5
    return dict(financials=summarize_company_facts(raw, ASOF),
                source_url='https://data.sec.gov/api/xbrl/companyfacts/CIK0000000001.json')


class FinancialReviewTests(unittest.TestCase):
    def test_fcf_identical_annual_periods_and_source_inputs(self):
        result = review(snapshot(), ASOF)
        fcf = result['annual']['free_cashflow']
        self.assertEqual(fcf['value'], 25)
        self.assertEqual(len(fcf['inputs']), 2)
        self.assertEqual(fcf['end'], '2025-12-31')
        self.assertIsNone(result['pe_last_fiscal_year'])
        self.assertIsNone(result['price_to_fcf_last_fiscal_year'])

    def test_ratios_only_with_existing_typed_reconciled_market_evidence(self):
        market = verified(['2026-05-12'])
        result = review(snapshot(), ASOF, market, 80)
        self.assertAlmostEqual(result['pe_last_fiscal_year'], 1e9/30)
        self.assertAlmostEqual(result['price_to_fcf_last_fiscal_year'], 1e9/25)
        self.assertAlmostEqual(result['distance_from_adjusted_insider_pct'], 25)
        self.assertIn('non TTM', result['multiple_basis'])
        self.assertFalse(result['buy_signal'])

    def test_positive_ocf_without_capex_is_not_fcf(self):
        s = snapshot();s['financials']['capex_years'] = []
        result = review(s, ASOF)
        self.assertIsNone(result['annual']['free_cashflow'])
        self.assertEqual(result['risks'], [])
        self.assertTrue(any('Capex' in text for text in result['missing']))

    def test_mismatched_periods_and_negative_capex_not_merged(self):
        s = snapshot();fin = s['financials']
        for row in fin['capex_years']:
            row['end'] = row['end'].replace('12-31', '12-30')
        self.assertEqual(free_cashflow(fin['cashflow_years'], fin['capex_years']), [])
        s = snapshot()
        for row in s['financials']['capex_years']:
            row['value'] = -5
        self.assertIsNone(review(s, ASOF)['annual']['free_cashflow'])

    def test_nonpositive_denominators_not_given_favorable_ratios(self):
        s = snapshot()
        for row in s['financials']['net_income_years']:
            row['value'] = -1
        for row in s['financials']['cashflow_years']:
            row['value'] = -1
        result = review(s, ASOF, verified(['2026-05-12']))
        self.assertIsNone(result['pe_last_fiscal_year'])
        self.assertIsNone(result['price_to_fcf_last_fiscal_year'])
        self.assertIn('Utile annuale negativo', result['risks'])
        self.assertIn('FCF annuale negativo', result['risks'])

    def test_no_unreviewed_total_income_or_client_market_flags(self):
        s = snapshot()
        for row in s['financials']['net_income_years']:
            row['tag'] = 'NetIncomeLoss'
        self.assertIsNone(review(s, ASOF, verified(['2026-05-12']))['pe_last_fiscal_year'])
        self.assertIsNone(review(s, ASOF, {'verified': True, 'price': 100})['pe_last_fiscal_year'])

    def test_zero_denominators_and_nonfinite_facts_remain_unverifiable(self):
        s = snapshot()
        for row in s['financials']['net_income_years']:
            row['value'] = 0
        for row in s['financials']['cashflow_years']:
            row['value'] = 5
        result = review(s, ASOF, verified(['2026-05-12']))
        self.assertEqual(result['annual']['free_cashflow']['value'], 0)
        self.assertIsNone(result['pe_last_fiscal_year'])
        self.assertIsNone(result['price_to_fcf_last_fiscal_year'])
        for row in s['financials']['cashflow_years']:
            row['value'] = float('nan')
        result = review(s, ASOF)
        self.assertIsNone(result['annual']['operating_cashflow'])
        self.assertIsNone(result['annual']['free_cashflow'])

    def test_future_fact_and_ytd_not_annualized(self):
        s = snapshot()
        for row in s['financials']['net_income_years']:
            row['filed'] = '2026-10-26'
        for row in s['financials']['capex_years']:
            row['start'] = row['end'][:4]+'-07-01'
        result = review(s, ASOF)
        self.assertIsNone(result['annual']['net_income'])
        self.assertIsNone(result['annual']['capex'])
        self.assertIsNone(result['annual']['free_cashflow'])

    def test_missing_debt_is_not_debt_zero(self):
        result = review(snapshot(), ASOF)
        self.assertIsNone(result['balance_observations']['debt_observation'])
        self.assertTrue(any('non debito zero' in x for x in result['missing']))
        self.assertFalse(result['certified_solid'])

    def test_actual_gpi_cache_offline_no_fake_fcf_or_price_comparison(self):
        s = json.loads((ROOT/'tests/fixtures/gpi-financial-cache-2026-10-25.json').read_text())
        original = copy.deepcopy(s)
        with patch('scanner.sec.get', side_effect=AssertionError('No new SEC acquisition')):
            result = review(s, ASOF)
        self.assertEqual(result['annual']['revenue']['value'], 22571400000)
        self.assertEqual(result['annual']['operating_cashflow']['value'], 694500000)
        self.assertIsNone(result['annual']['free_cashflow'])
        self.assertIsNone(result['distance_from_adjusted_insider_pct'])
        self.assertEqual(s, original)

    def test_real_cached_companies_are_not_claimed_market_qualified(self):
        pending = json.loads((ROOT/'docs/data/pending_index.json').read_text())['companies']
        radar = json.loads((ROOT/'docs/data/radar.json').read_text())
        reviews = {}
        for c in pending:
            path = ROOT/f'data/analysis/{c["cik"]}.json'
            reviews[c['cik']] = review(json.loads(path.read_text()) if path.exists() else None, radar['as_of'])
        result = report(pending, reviews, radar)
        self.assertEqual(result['counts']['insider_candidates'], len(pending))
        self.assertEqual(result['counts']['passed_insider_price_cap_filters'], 0)
        self.assertEqual(result['counts']['homepage_companies'], 0)
        self.assertGreater(result['counts']['candidates_with_cached_financials'], 0)


if __name__ == '__main__':
    unittest.main()
