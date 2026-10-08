import unittest,tempfile,copy
from pathlib import Path
from retail_research import run
class Tests(unittest.TestCase):
 def test_invalid_input_rejected_without_partial_report(self):
  for value in [None,dict(self.news(),extra=float('inf'))]:
   with tempfile.TemporaryDirectory() as directory:
    out=Path(directory)/'report'
    with self.assertRaises(ValueError):run(value,out)
    self.assertFalse(out.exists())
 def test_compact_cutoff_date_rejected(self):
  s=self.news();s['input']['asOf']='20261005'
  with self.assertRaises(ValueError):self.execute(s)
 def news(self):return dict(entry='news',input=dict(asOf='2026-10-05',currency='CNY',event=dict(entityId='stock:a',title='教学公告',source='教学来源',publishedAt='2026-10-01',acquiredAt='2026-10-02'),holdings=[dict(assetId='stock:a',assetClass='stock',currency='CNY',marketValue=40),dict(assetId='fund:b',assetClass='fund',currency='CNY',marketValue=60)]))
 def test_currency_mismatch_rejected(self):
  s=self.news();s['input']['holdings'][0]['currency']='USD'
  with self.assertRaises(ValueError):self.execute(s)
 def execute(self,s):
  with tempfile.TemporaryDirectory() as d:return run(s,Path(d)/'new')
 def test_news_direct_exposure_not_loss(self):
  r=self.execute(self.news())['result'];self.assertEqual(r['relatedWeightPct'],'40.0');self.assertEqual(r['status'],'related-for-research')
 def test_future_news_not_related(self):
  s=self.news();s['input']['event']['publishedAt']='2026-10-06';s['input']['event']['acquiredAt']='2026-10-06';r=self.execute(s)['result'];self.assertFalse(r['eligible']);self.assertEqual(r['relatedHoldings'],[])
 def test_no_match_not_no_impact(self):
  s=self.news();s['input']['event']['entityId']='stock:other';self.assertEqual(self.execute(s)['result']['status'],'no-known-direct-match')
 def test_holdings_reuses_constraints(self):
  from test_investment_intent import IntentTests
  t=IntentTests();t.setUp();r=self.execute(dict(entry='holdings',input=t.s));self.assertEqual(r['result']['type'],'investment-intent-review')
 def test_logic_missing_review_stays_unverified(self):
  from buy_side_thesis import freeze
  first=freeze(dict(entityId='stock:a',question='教学逻辑',asOf='2026-10-01',hypotheses=[dict(id='h1',claim='待检验判断',verificationMetric='收入',invalidation='回款下降',reviewBy='2026-11-01',evidence=[],gaps=['缺报告'])]))
  r=self.execute(dict(entry='logic',snapshot=first,input=dict(asOf='2026-10-05',assessments=[])));self.assertEqual(r['result']['assessments'][0]['outcome'],'unverified')
 def test_unknown_entry_rejected(self):
  with self.assertRaises(ValueError):self.execute(dict(entry='buy'))
if __name__=='__main__':unittest.main()
