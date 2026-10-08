import copy,unittest
from fund_evaluation import evaluate
def sample():
    proof={'sourceUrl':'https://example.org/report','publishedAt':'2026-01-10','locator':'p1'}
    return {'code':'a','asOf':'2026-10-03','reports':[{**proof,'reportDate':'2026-01-04','scope':'all-classes','netAssetsCNY':40_000_000,'holderCount':100,'institutionPct':10}],
            'historySourceUrl':'https://example.org/nav','historyBasis':'total-return','history':[{'date':f'2026-01-0{i}','value':v} for i,v in enumerate([1,1.1,.9,1.2],1)],
            'managers':[{**proof,'name':'one','start':'2026-01-01','confirmedThrough':'2026-01-03'}, {**proof,'name':'two','start':'2026-01-02','confirmedThrough':'2026-01-04'}]}
class Tests(unittest.TestCase):
    def test_annualization_overflow_keeps_observed_return(self):
        s=sample();s['history']=s['history'][:2];s['history'][1]['value']=1e100
        result=evaluate(s)['managerPeriods'][0]
        self.assertIsNone(result['metrics']['annualizedReturnPct']);self.assertTrue(result['metrics']['totalReturnPct']>0);self.assertIn('超过',result['annualizedReturnUnavailableReason'])
    def test_bad_evidence_locator_and_shape(self):
        s=sample();s['managers'][0]['locator']=True
        with self.assertRaises(ValueError):evaluate(s)
        for value in [None,[],dict(code='a',asOf='2026-10-03',history=[None])]:
            with self.subTest(value=value),self.assertRaises(ValueError):evaluate(value)
    def test_tenure_clip_and_overlap(self):
        r=evaluate(sample());a=r['managerPeriods'][0]
        self.assertEqual(a['actualEnd'],'2026-01-03');self.assertAlmostEqual(a['metrics']['totalReturnPct'],-10)
        self.assertEqual(len(a['coManagementIntervals']),1)
        self.assertEqual(len(r['structure'][0]['thresholdSignals']),2)
    def test_missing_not_complete(self):
        r=evaluate({'code':'a','asOf':'2026-10-03'});self.assertTrue(r['missing']);self.assertEqual(r['managerPeriods'],[])
    def test_support_boolean_rejected(self):
        s=sample();s['supportingResults']={'peerComparison':True}
        with self.assertRaises(ValueError):evaluate(s)
    def test_future_and_bad_share_rejected(self):
        s=sample();s['reports'][0]['institutionPct']=110
        with self.assertRaises(ValueError):evaluate(s)
        s=sample();s['managers'][0]['confirmedThrough']='2026-10-04'
        with self.assertRaises(ValueError):evaluate(s)
    def test_scope_change_prevents_size_delta(self):
        s=sample();r=copy.deepcopy(s['reports'][0]);r.update(reportDate='2026-01-05',scope='A',netAssetsCNY=20_000_000);s['reports'].append(r)
        self.assertIsNone(evaluate(s)['structure'][-1]['netAssetsChangePct'])
if __name__=='__main__':unittest.main()
