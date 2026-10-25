"""Real SEC observations plus rejection cases. No invented prices or market caps."""
import json
import unittest
import shutil
import tempfile
from datetime import date
from unittest.mock import patch
from pathlib import Path
from research.audit_market_data import reported_shares, audit, refresh_sample

ROOT = Path(__file__).resolve().parents[1]


class MarketAvailability(unittest.TestCase):
    def setUp(self):
        self.concept = json.loads((ROOT / 'research/market-sample/1031203-shares.json').read_text())['data']

    def test_actual_group_one_cover_shares(self):
        # Original 10-Q: 0001031203-26-000123, cover page, 24 July 2026.
        result = reported_shares(self.concept, '2026-08-01')['observation']
        self.assertEqual(result['shares'], 11922225)
        self.assertEqual(result['share_date'], '2026-07-24')
        self.assertEqual(result['accession'], '0001031203-26-000123')
        self.assertFalse(result['class_scope_verified'])
        self.assertFalse(result['split_basis_verified'])

    def test_future_filings_not_available_in_purchase_week(self):
        result = reported_shares(self.concept, '2026-07-24')['observation']
        self.assertLess(result['share_date'], '2026-07-24')
        self.assertLessEqual(result['public_on'], '2026-07-24')

    def test_missing_share_data_never_zero(self):
        self.concept['units'] = {}
        self.assertIsNone(reported_shares(self.concept, '2026-10-25')['observation'])

    def test_conflicting_class_or_restatement_not_summed(self):
        row = dict(reported_shares(self.concept, '2026-08-01')['observation'])
        base = {'end': row['share_date'], 'filed': row['public_on'], 'form': '10-Q',
                'accn': row['accession'], 'val': row['shares']}
        self.concept['units']['shares'] = [base, dict(base, val=base['val'] + 1)]
        self.assertEqual(reported_shares(self.concept, '2026-08-01')['status'], 'conflicting_observations')

    def test_reject_weighted_average_shares_and_public_float(self):
        for tag in ('WeightedAverageNumberOfDilutedSharesOutstanding', 'EntityPublicFloat'):
            self.concept['tag'] = tag
            self.assertIsNone(reported_shares(self.concept, '2026-10-25')['observation'])

    def test_invalid_dates(self):
        with self.assertRaises(ValueError):
            reported_shares(self.concept, '2026-02-30')

    def test_wrong_units_no_substitution(self):
        self.concept['units'] = {'USD': self.concept['units']['shares']}
        self.assertIsNone(reported_shares(self.concept, '2026-10-25')['observation'])

    def test_actual_abbott_empty_companyconcept(self):
        concept = json.loads((ROOT / 'research/market-sample/1800-shares.json').read_text())['data']
        self.assertIsNone(reported_shares(concept, '2026-10-25')['observation'])

    def test_actual_berkshire_stale_observation_not_current(self):
        concept = json.loads((ROOT / 'research/market-sample/1067983-shares.json').read_text())['data']
        row = reported_shares(concept, '2026-10-25')['observation']
        self.assertEqual(row['share_date'], '2011-04-29')
        self.assertGreater(row['age_days'], 5000)
        self.assertFalse(row['same_date_as_target'])
        self.assertFalse(row['class_scope_verified'])

    def test_real_sample_keeps_capitalizations_unknown(self):
        result = audit()
        self.assertEqual(result['counts']['sample_companies'], 3)
        self.assertFalse(result['production_integration_enabled'])
        self.assertEqual(result['counts']['newly_verified_capitalizations'], 0)
        for row in result['sample']:
            self.assertIsNone(row['historical_capitalization'])
            self.assertIsNone(row['current_capitalization'])

    def test_cached_sample_makes_no_network_requests(self):
        with patch('scanner.sec.get') as get:
            refresh_sample(today=date(2026, 10, 26))
        get.assert_not_called()

    def test_refresh_failure_preserves_previous_sample(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / 'research/market-sample', root / 'research/market-sample')
            path = root / 'research/market-sample/1800-shares.json'
            previous = path.read_bytes()
            with patch('scanner.sec.get', side_effect=RuntimeError('network unavailable')):
                with self.assertRaises(RuntimeError):
                    refresh_sample(root, today=date(2026, 11, 2))
            self.assertEqual(path.read_bytes(), previous)

    def test_refresh_requests_only_six_sec_endpoints(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def response(url, **kwargs):
                cik = int(url.split('CIK')[1].split('/')[0].split('.')[0])
                kind = 'identity' if '/submissions/' in url else 'shares'
                data = json.loads((ROOT / f'research/market-sample/{cik}-{kind}.json').read_text())['data']
                # Identity snapshot is a projection, reconstruct only fields used here.
                if kind == 'identity':
                    data = dict(data, filings={'recent': {'form': []}})
                return json.dumps(data).encode()
            with patch('scanner.sec.get', side_effect=response) as get:
                refresh_sample(root, today=date(2026, 10, 25))
            self.assertEqual(get.call_count, 6)
            self.assertTrue(all('data.sec.gov/' in c.args[0] for c in get.call_args_list))
            self.assertFalse(any('.zip' in c.args[0] for c in get.call_args_list))


if __name__ == '__main__':
    unittest.main()
