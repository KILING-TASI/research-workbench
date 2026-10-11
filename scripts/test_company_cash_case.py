import unittest,copy
from unittest.mock import patch
from company_cash_case import review

class Tests(unittest.TestCase):
    def sample(self):
        fact={'source':'https://example.org/a','publishedAt':'2026-01-01','evidence':{'documentSha256':'0'*64}}
        row=dict(id='operatingCashFlow',status='available',reason='test',source=fact['source'],locator='1',sourceVersion='1',publishedDate='2026-01-01',acquiredAt='2026-01-02T00:00:00Z',rawSourceSha256='0'*64,dataDate='2025-12-31',valueType='disclosed')
        return {'inputSchema':'company-cash-case/1','question':'q','evidence':{'inputSchema':'evidence-status/1','question':'q','asOfDate':'2026-10-11','asOf':'2026-10-11T23:59:59Z','maxAgeDays':400,'records':[row]},'financialInput':{'asOf':'2026-10-11','facts':{'operatingCashFlow':fact}}}
    def test_mismatched_source_blocked_before_calculation(self):
        s=self.sample();s['financialInput']['facts']['operatingCashFlow']['source']='https://example.org/b'
        with patch('company_cash_case.call') as fn:
            with self.assertRaisesRegex(ValueError,'来源'):review(s)
            fn.assert_not_called()
    def test_missing_record_cannot_bypass_gate(self):
        s=self.sample();s['evidence']['records']=[]
        with self.assertRaisesRegex(ValueError,'每个财报'):review(s)
    def test_failed_value_withheld_not_zero(self):
        s=self.sample();s['evidence']['records'][0]['status']='failed'
        result={'amounts':{},'cashSurplus':None,'coverage':{'declaredDividend':{'cashSurplusCoverage':None}}}
        with patch('company_cash_case.call',return_value=result) as fn,patch.dict('company_cash_case.LAST_PROVENANCE',{'financial':{}}):
            r=review(s);self.assertIsNone(fn.call_args.args[3]['facts']['operatingCashFlow']);self.assertEqual(r['withheldMetrics'],['operatingCashFlow'])
