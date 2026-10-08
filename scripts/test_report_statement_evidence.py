import unittest
from report_statement_evidence import bind


class Tests(unittest.TestCase):
    def test_source_date_and_statement_shape(self):
        for key,value in [('sourceUrl','https://user:password@example.org/a'),('publishedAt','20260831'),('statements',[None])]:
            s=self.spec();s[key]=value
            with self.assertRaises(ValueError):bind(s,{11:'内需方向承压'},'abc')
    def spec(self):
        return dict(sha256='abc',reportType='interim',purpose='report-statements',
                    periodEnd='2026-06-30',publishedAt='2026-08-31',asOf='2026-10-06',
                    provenance='third-party-report-copy',sourceUrl='https://example.org/report.pdf',
                    statements=[dict(id='explanation',page=11,quote='内需方向承压',category='retrospective-explanation')])

    def test_statement_does_not_certify_cause(self):
        r=bind(self.spec(),{11:'内需方向 承压'},'abc')
        self.assertTrue(r['statements'][0]['textMatch'])
        self.assertFalse(r['statements'][0]['independentFactVerified'])

    def test_interim_not_annual_views(self):
        s=self.spec();s['purpose']='manager-annual-views'
        with self.assertRaises(ValueError):bind(s,{11:'内需方向承压'},'abc')

    def test_unmatched_quote_and_version_rejected(self):
        with self.assertRaises(ValueError):bind(self.spec(),{11:'其他内容'},'abc')
        with self.assertRaises(ValueError):bind(self.spec(),{11:'内需方向承压'},'changed')

    def test_future_publication_rejected(self):
        s=self.spec();s['publishedAt']='2026-11-01'
        with self.assertRaises(ValueError):bind(s,{11:'内需方向承压'},'abc')
