import copy
import unittest
import tempfile, json, hashlib
from pathlib import Path
from unittest.mock import patch, Mock
from nav_crosscheck import compare, compare_period_return, resolve_period_paths


class NavCrosscheckTests(unittest.TestCase):
    def spec(self):
        source = dict(url='https://example.org/nav', code='006228', basis='unit-nav',
                      retrievedAt='2026-10-06T00:00:00Z', observations=[
                          dict(date='2026-09-30', nav='1.7966', excerpt='2026-09-30 1.7966')])
        return dict(code='006228', asOf='2026-10-06', sources=[source, copy.deepcopy(source)])

    def test_selected_match_does_not_certify_completeness(self):
        r=compare(self.spec()); self.assertEqual(r['matchedCount'],1)
        self.assertFalse(r['fullHistoryVerified']); self.assertFalse(r['dividendCompletenessVerified'])

    def test_conflict_retained(self):
        s=self.spec(); s['sources'][1]['observations'][0].update(nav='1.7965',excerpt='2026-09-30 1.7965')
        r=compare(s); self.assertEqual(r['status'],'selected-observations-conflict')
        self.assertEqual(Decimal(r['rows'][0]['difference']),Decimal('0.0001'))

    def test_duplicate_rejected(self):
        s=self.spec(); s['sources'][0]['observations']*=2
        with self.assertRaises(ValueError):compare(s)

    def test_basis_rejected(self):
        s=self.spec(); s['sources'][1]['basis']='accumulated-nav'
        with self.assertRaises(ValueError):compare(s)

    def test_nav_excerpt_requires_complete_number(self):
        for quote in ['2026-09-30 21.7966', '2026-09-30 1.7966%', '2026-09-30 1.7966e2']:
            s=self.spec();s['sources'][0]['observations'][0]['excerpt']=quote
            with self.subTest(quote=quote), self.assertRaises(ValueError):compare(s)

    def test_nav_requires_plain_decimal(self):
        for value in ['1e2',' 1.7966','NaN']:
            s=self.spec();s['sources'][0]['observations'][0].update(nav=value,excerpt='2026-09-30 '+value)
            with self.subTest(value=value), self.assertRaises(ValueError):compare(s)


from decimal import Decimal


class PeriodReturnTests(unittest.TestCase):
    def test_relative_archives_follow_input_directory(self):
        spec = dict(unitNavFile='data/nav.json', pdfFile='reports/report.pdf')
        resolved = resolve_period_paths(spec, '/task')
        self.assertEqual(Path(resolved['unitNavFile']), Path('/task/data/nav.json'))
        self.assertEqual(spec['unitNavFile'], 'data/nav.json')

    def test_empty_archive_path_rejected(self):
        with self.assertRaises(ValueError):
            resolve_period_paths(dict(unitNavFile='', pdfFile='report.pdf'), '/task')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.nav = Path(self.tmp.name)/'nav.json'; self.pdf = Path(self.tmp.name)/'report.pdf'
        self.pdf.write_bytes(b'pdf-fixture')
        self.history = dict(code='000991', historyBasis='nav-with-distributions', history=[
            dict(date='2025-12-31',nav=1),dict(date='2026-06-30',nav=1.1)])
        self.spec = dict(code='000991',shareClass='A',periodStart='2026-01-01',periodEnd='2026-06-30',
            baselineDate='2025-12-31',unitNavFile=str(self.nav),pdfFile=str(self.pdf),
            pdfFileSha256=hashlib.sha256(self.pdf.read_bytes()).hexdigest(),reportedReturnPct='10.00',
            periodEvidence=dict(page=1,quote='本报告期自2026年01月01日起至2026年06月30日止'),
            performanceEvidence=dict(page=1,quote='基金A类份额净值增长率为10.00%'),
            noDistributionEvidence=dict(page=1,quote='本基金本报告期未进行利润分配'))
        text='\n'.join(self.spec[k]['quote'] for k in ['periodEvidence','performanceEvidence','noDistributionEvidence'])
        self.mock=patch('pypdf.PdfReader',return_value=Mock(pages=[Mock(extract_text=lambda:text)]))
        self.mock.start(); self.addCleanup(self.mock.stop)

    def run_check(self):
        self.nav.write_text(json.dumps(self.history),encoding='utf-8')
        self.spec['unitNavFileSha256']=hashlib.sha256(self.nav.read_bytes()).hexdigest()
        return compare_period_return(self.spec)

    def test_same_period_rounded_match_not_full_certification(self):
        r=self.run_check();self.assertEqual(r['status'],'selected-period-rounded-match')
        self.assertFalse(r['fullHistoryVerified']);self.assertEqual(r['baselineNav'],'1')

    def test_missing_baseline_and_duplicate_rejected(self):
        self.history['history'].pop(0)
        with self.assertRaises(ValueError):self.run_check()
        self.history['history'].append(self.history['history'][0])
        with self.assertRaises(ValueError):self.run_check()

    def test_conflicting_distribution_event_rejected(self):
        self.history['history'][-1]['distribution']='每份分红0.1元'
        with self.assertRaises(ValueError):self.run_check()

    def test_mismatch_retained(self):
        self.history['history'][-1]['nav']=1.2
        self.assertEqual(self.run_check()['status'],'selected-period-conflict')

    def test_wrong_baseline_and_unchanged_hash_rejected(self):
        self.spec['baselineDate']='2026-01-02'
        with self.assertRaises(ValueError):self.run_check()
        self.spec['baselineDate']='2025-12-31';self.run_check();self.pdf.write_bytes(b'changed')
        with self.assertRaises(ValueError):self.run_check()

    def test_unscoped_no_distribution_not_current_period(self):
        self.spec['noDistributionEvidence']['quote']='未进行利润分配'
        with self.assertRaises(ValueError):self.run_check()

    def test_explicit_other_end_year_not_short_date_match(self):
        self.spec['periodEvidence']['quote']='本报告期自2026年01月01日起至2025年06月30日止'
        text='\n'.join(self.spec[k]['quote'] for k in ['periodEvidence','performanceEvidence','noDistributionEvidence'])
        with patch('pypdf.PdfReader',return_value=Mock(pages=[Mock(extract_text=lambda:text)])):
            with self.assertRaises(ValueError):self.run_check()

    def test_return_substring_not_full_number(self):
        self.spec['performanceEvidence']['quote']='基金A类份额净值增长率为110.00%'
        text='\n'.join(self.spec[k]['quote'] for k in ['periodEvidence','performanceEvidence','noDistributionEvidence'])
        with patch('pypdf.PdfReader',return_value=Mock(pages=[Mock(extract_text=lambda:text)])):
            with self.assertRaises(ValueError):self.run_check()

    def test_other_share_return_in_same_quote_rejected(self):
        self.spec['performanceEvidence']['quote']='基金A类份额净值增长率为20.00%；基金C类份额净值增长率为10.00%'
        text='\n'.join(self.spec[k]['quote'] for k in ['periodEvidence','performanceEvidence','noDistributionEvidence'])
        with patch('pypdf.PdfReader',return_value=Mock(pages=[Mock(extract_text=lambda:text)])):
            with self.assertRaises(ValueError):self.run_check()

class StrictInputsTests(unittest.TestCase):
    def test_noncanonical_dates_rejected(self):
        from nav_crosscheck import iso_day
        for value in ['20261006','2026-W41-2',None,'2026-02-30']:
            with self.assertRaises(ValueError):iso_day(value)
    def test_duplicate_and_nonfinite_json_rejected(self):
        from nav_crosscheck import load_json
        for text in ['{"nav":1,"nav":2}','{"nav":NaN}','{"nav":1e999}']:
            with self.assertRaises(ValueError):load_json(text)
