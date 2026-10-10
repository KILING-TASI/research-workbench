# SPDX-License-Identifier: MIT
import copy,unittest
from disclosure_review import review

def record(id='a',facts=None):
    return {'id':id,'entity':'原创教学公司','stage':'announced','source':'https://example.invalid/teaching','locator':'原创教学第1行','sourceVersion':'teaching-1','rawSourceSha256':'0'*64,'publishedDate':'2025-02-01','acquiredAt':'2025-02-02T08:00:00+08:00','facts':facts or {'observedDate':'2025-01-31','count':'100','shareClass':'A','scope':'登记持有人'}}
class DisclosureTests(unittest.TestCase):
    def spec(self,rows,topic='shareholders'):return {'asOf':'2025-03-01T08:00:00+08:00','topic':topic,'entity':'原创教学公司','records':rows}
    def test_shareholder_comparison(self):
        a=record();b=record('b',dict(a['facts'],observedDate='2025-02-01',count='80'))
        result=review(self.spec([a,b]));self.assertEqual(result['shareholderChanges'][0]['countDifference'],'-20')
    def test_scope_is_not_merged(self):
        a=record();b=record('b',dict(a['facts'],scope='不同范围',observedDate='2025-02-01'))
        self.assertEqual(review(self.spec([a,b]))['shareholderChanges'],[])
    def test_cutoff(self):
        a=record();a['acquiredAt']='2025-04-01T08:00:00+08:00'
        self.assertEqual(review(self.spec([a]))['excludedAfterCutoffIds'],['a'])
    def test_invalid_counts(self):
        for value in ['1.2','-1','NaN']:
            with self.assertRaises(ValueError):review(self.spec([record(facts=dict(record()['facts'],count=value))]))
    def test_forecast_negative_base(self):
        f={'periodStart':'2025-01-01','periodEnd':'2025-12-31','metric':'netProfit','profitAttribution':'parent','scope':'consolidated','currency':'CNY','unit':'万元','lower':'10','upper':'20','previousActual':'-10'}
        result=review(self.spec([record(facts=f)],'earnings-forecast'))
        self.assertEqual(result['records'][0]['changeVsPrevious'],['2','3'])
        f['previousActual']='0';self.assertIsNone(review(self.spec([record(facts=f)],'earnings-forecast'))['records'][0]['changeVsPrevious'])
    def test_plan_cannot_be_implementation(self):
        row=record(facts={'eventDate':None,'publicStatement':'拟解禁，教学','denominator':None,'implementationEvidence':None});row['stage']='implemented'
        with self.assertRaises(ValueError):review(self.spec([row],'unlock'))
    def test_duplicates_and_missing_evidence(self):
        with self.assertRaises(ValueError):review(self.spec([record(),record()]))
        row=record();del row['locator']
        with self.assertRaises(ValueError):review(self.spec([row]))

if __name__=='__main__':unittest.main()
