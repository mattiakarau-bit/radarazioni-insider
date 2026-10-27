import copy,json,unittest
from pathlib import Path
from scanner.quarterly import analyze,compact
ROOT=Path(__file__).resolve().parents[1]

def sample(cik):return json.loads((ROOT/f'research/quarterly-sample/{cik}.json').read_text())['data']

class QuarterlyTests(unittest.TestCase):
    def test_authentic_gpi_cashflow_is_quarter_not_ytd(self):
        raw=sample(1031203);r=analyze(raw,'2026-10-27',5511,True)
        c=r['series']['operating_cashflow'][-1];fcf=r['series']['free_cashflow'][-1]
        self.assertEqual((c['start'],c['end']),('2026-04-01','2026-06-30'))
        self.assertEqual(c['value'],62_600_000);self.assertEqual(fcf['value'],19_800_000)
        self.assertEqual(c['derivation'],'YTD_difference')
        self.assertEqual(c['filed'],'2026-07-30')

    def test_facts_not_public_at_event_excluded_and_same_day_rejected(self):
        raw=sample(1031203)
        r=analyze(raw,'2026-07-30',5511,True)
        self.assertLess(r['latest_period'],'2026-06-30')
        for rows in r['series'].values():self.assertTrue(all(x['filed']<'2026-07-30' for x in rows))

    def test_no_ytd_eps_subtraction(self):
        raw=sample(1031203)
        for tag in ('EarningsPerShareDiluted','EarningsPerShareBasic'):
            for unit,rows in raw['facts']['us-gaap'].get(tag,{}).get('units',{}).items():
                raw['facts']['us-gaap'][tag]['units'][unit]=[r for r in rows if r.get('start','').endswith('01-01') and r.get('end','').endswith('06-30')]
        self.assertEqual(analyze(raw,'2026-10-27',5511,True)['series']['eps'],[])

    def test_sector_scope_does_not_apply_industrial_margins_to_banks(self):
        raw=sample(1031203)
        self.assertEqual(analyze(raw,'2026-10-27',6020,True)['operating_margins_pct'],[])
        self.assertEqual(analyze(raw,'2026-10-27',6311,True)['sector_family'],'insurance')
        self.assertEqual(analyze(raw,'2026-10-27',6798,True)['sector_family'],'reit')
        self.assertEqual(analyze(raw,'2026-10-27',5511,False)['series']['revenue'],[])

    def test_authentic_compact_provenance_budget_and_stale_period(self):
        for cik in (1800,1031203,1060391):
            r=compact(analyze(sample(cik),'2026-10-27',5511,True),cik)
            self.assertLess(len(json.dumps(r)),22000)
            for rows in r['series'].values():
                for x in rows:
                    for ref in x.get('input_refs',[]):self.assertIn(ref,r['source_facts'])
            self.assertFalse(r['valuation_verified'])
        r=compact(analyze(sample(1800),'2026-10-27',2834,True),1800)
        self.assertFalse(r['fresh_latest_period'])
