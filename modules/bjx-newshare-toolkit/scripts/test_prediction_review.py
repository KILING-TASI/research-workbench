import unittest,tempfile,json,datetime as dt
from pathlib import Path
from unittest.mock import patch
from prediction_review import capture,review,compare
class Prediction(unittest.TestCase):
    def spec(self,folder,model='old'):
        p=Path(folder)/'source.json';p.write_text('{}')
        return {'modelVersion':model,'decisionCutoff':'2026-07-02T09:15:00+08:00','inputs':[{'path':str(p),'availableAt':'2026-06-30T00:00:00Z','retrievedAt':'2026-07-01T00:00:00Z'}],'allocation':{'code':'920022','price':'10','budget':'1000000','maxShares':200000,'ratesPct':{'P75':'0.2','P50':'0.1','P25':'0.05'},'rateBasis':'synthetic','gainPct':{'P75':10,'P50':0,'P25':-10},'applyDate':'2026-07-02','refundDate':'2026-07-04','saleSettlementDate':'2026-07-10'}}
    def clock(self,day):return patch('prediction_review.now',return_value=dt.datetime(2026,7,day,tzinfo=dt.timezone.utc))
    def test_first_capture_immutable(self):
        with tempfile.TemporaryDirectory() as f,self.clock(1):
            s=self.spec(f);capture(s,f);self.assertTrue(capture(s,f)['duplicate']);s['allocation']['budget']='2000000'
            with self.assertRaises(ValueError):capture(s,f)
    def test_past_only_replay(self):
        with tempfile.TemporaryDirectory() as f,self.clock(6):
            s=self.spec(f)
            with self.assertRaises(ValueError):capture(s,f)
            self.assertEqual(capture(s,f,True)['mode'],'historical-replay')
    def test_future_input(self):
        with tempfile.TemporaryDirectory() as f,self.clock(1):
            s=self.spec(f);s['inputs'][0]['availableAt']='2026-07-03T00:00:00Z'
            with self.assertRaises(ValueError):capture(s,f)
    def test_review_and_same_sample(self):
        with tempfile.TemporaryDirectory() as f:
            with self.clock(1):
                for model in ['old','new']:capture(self.spec(f,model),f)
            actual=Path(f)/'actual.json';actual.write_text('{}');paths=[]
            with self.clock(6):
                for model in ['old','new']:
                    p=Path(f)/'research-data/bjx-predictions/frozen'/model/'920022/first.json'
                    r=review({'predictionPath':str(p),'actual':{'code':'920022','publishedAt':'2026-07-05T00:00:00Z','ratePct':'0.1','sourcePath':str(actual),'allocatedShares':100,'cashflowsComplete':True,'cashflows':[{'date':'2026-07-02','kind':'subscription','amount':'-1000000'},{'date':'2026-07-04','kind':'refund','amount':'999000'},{'date':'2026-07-05','kind':'settlement','amount':'1200'}]}},f)
                    self.assertEqual(r['cashflowReview']['netCashFlow'],'200');self.assertIsNotNone(r['cashflowReview']['scenarioNetProfitErrors'])
                    dest=Path(f)/(model+'.json');dest.write_text(json.dumps(r));paths.append(str(dest))
            result=compare({'before':[paths[0]],'after':[paths[1]]});self.assertEqual(result['commonCount'],1);self.assertEqual(result['summary']['before']['P50']['MAE'],'0');self.assertFalse(result['automaticReplacement'])
    def test_input_tamper(self):
        with tempfile.TemporaryDirectory() as f:
            with self.clock(1):capture(self.spec(f),f)
            p=Path(f)/'research-data/bjx-predictions/frozen/old/920022/first.json';archive=next((p.parent/'inputs').glob('*.bin'));archive.write_bytes(b'changed')
            with self.clock(6),self.assertRaises(ValueError):review({'predictionPath':str(p),'actual':{}},f)
if __name__=='__main__':unittest.main()
