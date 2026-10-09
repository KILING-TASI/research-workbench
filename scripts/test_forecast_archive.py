import copy
import json
from pathlib import Path
import tempfile
import unittest
from forecast_archive import calculate, publish


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
