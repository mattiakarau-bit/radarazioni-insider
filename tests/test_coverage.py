import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scanner.coverage import merge_pending, select_queue, record_failure, coverage_report
from scanner.sec import discover, read_master_index
from scanner.identity import filing_key
from scanner import run


def filing(n, day='2026-10-23'):
    return dict(cik=1, company='Test', filed=day, url=f'https://www.sec.gov/Archives/edgar/data/1/0000000001-26-{n:06d}.txt')

class CoverageTests(unittest.TestCase):
    def test_fairness_and_durable_backlog(self):
        old=[filing(i,'2026-09-01') for i in range(1,8)]
        fresh=[filing(i) for i in range(10,20)]
        pending=merge_pending(old,fresh,set())
        queue=select_queue(pending,6,'2026-10-24')
        self.assertEqual(sum(x['filed']=='2026-09-01' for x in queue),2)
        self.assertEqual(sum(x['filed']=='2026-10-23' for x in queue),4)
        seen={filing_key(x['url']) for x in queue}
        self.assertEqual(len(merge_pending(pending,[],seen)),11)
    def test_retry_does_not_block_oldest_lane(self):
        bad=filing(1,'2026-09-01'); record_failure(bad,'2026-10-24','invalid XML')
        self.assertEqual(select_queue([bad],6,'2026-10-24'),[])
        self.assertEqual(len(select_queue([bad],6,'2026-10-25')),1)
    def test_failed_index_retained_and_cursor_advances(self):
        state={}
        with patch('scanner.sec.read_master_index',side_effect=ValueError('offline')):
            rows,checked,errors=discover(state,2,'2026-10-24T12:00:00+00:00')
        self.assertFalse(checked)
        self.assertIn('2026-10-22',state['index_retries'])
        self.assertEqual(state['backfill_cursor'],'2026-10-21')
        with patch('scanner.sec.read_master_index',return_value=[]):
            discover(state,2,'2026-10-25T12:00:00+00:00')
        self.assertFalse(state['index_retries'])
    def test_invalid_index_not_empty_success(self):
        from datetime import date
        with patch('scanner.sec.get',return_value='<html>Error</html>'):
            with self.assertRaises(ValueError):read_master_index(date(2026,10,23))
    def test_real_run_persists_failure_and_retries_without_notifications(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            paths={k:root/(k+'.json') for k in ('STATE','RESULTS','HISTORY','MODEL')}
            good,bad=filing(1),filing(2)
            def discovery(state,days,now):
                state.update(indexes={'2026-10-23':dict(url='https://www.sec.gov/index',checked_utc=now,accessions=[filing_key(good['url']),filing_key(bad['url'])])},index_retries=[],backfill_cursor='2026-10-16')
                return [good,bad],['2026-10-23'],[]
            with patch.multiple(run,**paths),patch.object(run,'discover',side_effect=discovery),patch.object(run,'get',side_effect=['valid','broken']),patch.object(run,'parse_form4',side_effect=[[],ValueError('XML invalid')]),patch.object(run,'send_telegram') as notify:
                run.main()
                state=json.loads(paths['STATE'].read_text()); result=json.loads(paths['RESULTS'].read_text())
                self.assertEqual(len(state['pending']),1)
                self.assertEqual(state['pending'][0]['attempts'],1)
                self.assertEqual(result['coverage']['known_processed_forms'],1)
                self.assertEqual(result['coverage']['known_completion_pct'],50)
                notify.assert_not_called()
    def test_alias_dedup(self):
        a=filing(1); b=dict(a,url=a['url'].replace('/1/','/2/'))
        self.assertEqual(len(merge_pending([a],[b],set())),1)
    def test_downtime_days_and_failed_indexes_not_lost(self):
        state={'last_discovery_day':'2026-10-01','index_retries':['2020-01-01','2020-01-02','2020-01-03'],'index_attempts':{d:'2026-10-23T00:00:00+00:00' for d in ['2020-01-01','2020-01-02','2020-01-03']}}
        with patch('scanner.sec.read_master_index',return_value=[]):
            discover(state,2,'2026-10-24T12:00:00+00:00')
        self.assertIn('2026-10-15',state['index_retries'])
        self.assertIn('2020-01-01',state['index_retries'])
        self.assertIn('2026-10-01',state['indexes'])
    def test_backfill_pauses_when_queue_is_loaded(self):
        state={'pending':[filing(i) for i in range(400)],'backfill_cursor':'2026-09-01'}
        with patch('scanner.sec.read_master_index',return_value=[]) as read:
            discover(state,2,'2026-10-24T12:00:00+00:00')
        self.assertEqual(state['backfill_cursor'],'2026-09-01')
        self.assertNotIn('2026-09-01',state['indexes'])
