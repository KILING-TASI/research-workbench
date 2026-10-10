import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from forecast_archive import calculate, publish, METHOD


class TestForecastArchive(unittest.TestCase):
    def setUp(self):
        row = dict(id='first', entity='教学公司', institution='教学机构', reportId='R1', metric='parentNetProfit', currency='CNY',
                   reportVersion='v1', sourceVersion='web-v1', sourceTier='teaching-only', source='https://example.org/teaching',
                   rawSourceSha256='0'*64, publishedDate='2026-01-01', publishedTimePrecision='date-only',
                   acquiredAt='2026-02-01T10:00:00+08:00', knownAvailableAt=None, forecastPeriod='2026-12-31',
                   unit='亿元', value=10, scope='consolidated', basis='annual-forecast', profitAttribution='parent-owners', shareBasis=None)
        self.s = dict(inputSchema='forecast-observations-v1', methodVersion='acquisition-bound-history-1', asOf='2026-02-02T10:00:00+08:00', records=[row])
    def test_publication_is_not_acquisition(self):
        self.s['asOf']='2026-01-10T10:00:00+08:00'
        self.assertEqual(calculate(self.s)['observations'],[])
        self.assertEqual(len(calculate(self.s)['excluded']),1)
    def test_same_report_source_conflict_is_not_revision(self):
        row=copy.deepcopy(self.s['records'][0]);row.update(id='second',value=11,sourceVersion='web-v2',supersedesId='first',revisionEvidence='教学来源声明')
        self.s['records'].append(row)
        r=calculate(self.s);self.assertEqual(r['observations'][0]['status'],'source-value-conflict');self.assertIsNone(r['revisions'][0]['difference'])
        self.assertEqual(r['observations'][0]['reportVersion'],'v1')
        self.assertTrue(all(v['reportVersion']=='v1' for v in r['observations'][0]['values']))
    def test_different_declared_report_versions_remain_separate(self):
        self.s['records'][0]['reportVersion']='original'
        row=copy.deepcopy(self.s['records'][0]);row.update(id='second',reportVersion='corrected-v2',value=11,
            supersedesId='first',revisionEvidence='声明更正，未核原文')
        self.s['records'].append(row)
        result=calculate(self.s)
        self.assertEqual(len(result['observations']),2)
        self.assertEqual({r['reportVersion'] for r in result['observations']},{'original','corrected-v2'})
        self.assertTrue(all(r['status']=='single-observation' and r['reportVersionStatus']=='declared-only' for r in result['observations']))
        self.assertEqual(result['revisions'][0]['status'],'declared-report-version-change-not-analyst-revision')
        self.assertIsNone(result['revisions'][0]['difference'])
        self.assertEqual(result['revisions'][0]['priorReportVersion'],'original')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);publish(self.s,root/'archive',root/'report')
            body=(root/'report'/'预测留档.md').read_text('utf-8')
            self.assertIn('声明报告版本original（未核原文）',body)
            self.assertIn('声明报告版本corrected-v2（未核原文）',body)
    def test_request_duplicate_rejected_even_when_id_is_stored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);publish(self.s,root/'archive',root/'report1')
            before={p.name:p.read_bytes() for p in (root/'archive').iterdir()}
            self.s['records']*=2
            with self.assertRaisesRegex(ValueError,'观察标识重复'):calculate(self.s)
            with patch('forecast_archive.load',side_effect=AssertionError('must validate before archive read')):
                with self.assertRaisesRegex(ValueError,'观察标识重复'):
                    publish(self.s,root/'archive',root/'report2')
            self.assertEqual({p.name:p.read_bytes() for p in (root/'archive').iterdir()},before)
            self.assertFalse((root/'report2').exists())
    def test_request_schema_and_method_checked_before_archive_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);publish(self.s,root/'archive',root/'report1')
            for key,value in [('inputSchema','future-schema'),('methodVersion','future-method')]:
                changed=copy.deepcopy(self.s);changed[key]=value
                with patch('forecast_archive.load',side_effect=AssertionError('must validate before archive read')):
                    with self.assertRaisesRegex(ValueError,'未知显式档案'):
                        publish(changed,root/'archive',root/'report2')
                self.assertFalse((root/'report2').exists())
    def test_legacy_request_explicitly_reports_corrected_method(self):
        legacy=calculate(self.s)
        self.assertEqual(legacy['requestedMethodVersion'],'acquisition-bound-history-1')
        self.assertEqual(legacy['methodVersion'],METHOD)
        self.assertEqual(legacy['inputCompatibility'],'legacy-v1-input-under-corrected-v2-not-v1-output-replay')
        self.s['methodVersion']=METHOD
        self.assertEqual(calculate(self.s)['inputCompatibility'],'current-v2')
    def test_same_day_new_report_order_unknown(self):
        row=copy.deepcopy(self.s['records'][0]);row.update(id='second',reportId='R2',value=11,supersedesId='first',revisionEvidence='教学来源声明')
        self.s['records'].append(row)
        self.assertEqual(calculate(self.s)['revisions'][0]['status'],'same-day-or-reversed-order-unknown')
    def test_revision_unit_conversion_and_unknown_basis(self):
        row=copy.deepcopy(self.s['records'][0]);row.update(id='second',reportId='R2',publishedDate='2026-01-02',value=110000,unit='万元',supersedesId='first',revisionEvidence='教学来源声明')
        self.s['records'].append(row)
        self.assertEqual(calculate(self.s)['revisions'][0]['difference'],'100000000')
        self.s['records'][1]['scope']=None
        self.assertIsNone(calculate(self.s)['revisions'][0]['difference'])
    def test_archive_id_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);publish(self.s,root/'archive',root/'report1')
            old=list((root/'archive').glob('*.json'))[0].read_bytes()
            self.s['records'][0]['value']=11
            with self.assertRaises(ValueError):publish(self.s,root/'archive',root/'report2')
            self.assertEqual(list((root/'archive').glob('*.json'))[0].read_bytes(),old)
            self.assertFalse((root/'report2').exists())
    def test_unknown_version_and_backdated_availability_refused(self):
        self.s['methodVersion']='future-v9'
        with self.assertRaises(ValueError):calculate(self.s)
        self.s['methodVersion']='acquisition-bound-history-1';self.s['records'][0]['knownAvailableAt']='2026-01-01T00:00:00+08:00'
        with self.assertRaises(ValueError):calculate(self.s)
    def test_publication_day_uses_china_timezone(self):
        self.s['records'][0]['acquiredAt']='2025-12-31T16:30:00+00:00'
        self.assertEqual(len(calculate(self.s)['observations']),1)
