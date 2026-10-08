import unittest,json
from fund_details import extract
class Tests(unittest.TestCase):
 def raw(self,changes=None):
  x={'fS_code':'000001','fS_name':'测试基金','Data_netWorthTrend':[{'x':1735689600000,'y':1,'unitMoney':''},{'x':1735776000000,'y':1.1,'unitMoney':''}],'Data_assetAllocation':{'categories':['2025-01-01','2026-01-01'],'series':[{'name':'股票占净比','data':[90,95]}]},'Data_currentFundManager':[{'name':'某经理','star':5,'workTime':'10年'}]}
  x.update(changes or {});return '\n'.join('var '+k+'='+json.dumps(v,ensure_ascii=False)+';' for k,v in x.items())
 def test_future_filtered(self):
  r=extract(self.raw(),'000001','2025-01-03',None);self.assertEqual(len(r['facts']['assetAllocation']['observations']),1)
 def test_no_rating(self):
  r=extract(self.raw(),'000001','2025-01-03',None);self.assertNotIn('star',r['facts']['managerClues']['value'][0]);self.assertFalse(r['facts']['managerClues']['historicalAsOfVerified'])
 def test_identity(self):
  with self.assertRaises(ValueError):extract(self.raw(),'000002','2025-01-03',None)
 def test_duplicate_nav(self):
  with self.assertRaises(ValueError):extract(self.raw({'Data_netWorthTrend':[{'x':1735689600000,'y':1}]*2}),'000001','2025-01-03',None)
 def test_unknown_split_blocks_metrics(self):
  x=[{'x':1735689600000,'y':1,'unitMoney':''},{'x':1735776000000,'y':2,'unitMoney':'未知拆分'}]
  r=extract(self.raw({'Data_netWorthTrend':x}),'000001','2025-01-03',None);self.assertTrue(all(p['metrics'] is None for p in r['stagePerformance']))
 def test_misaligned_structure(self):
  with self.assertRaises(ValueError):extract(self.raw({'Data_assetAllocation':{'categories':['2025-01-01'],'series':[{'name':'x','data':[]} ]}}),'000001','2025-01-03',None)
 def test_short_history_not_three_years(self):
  r=extract(self.raw(),'000001','2025-01-03',None);p=next(x for x in r['stagePerformance'] if x['months']==36);self.assertIsNone(p['metrics']);self.assertIn('未覆盖',p['status'])
 def test_stale_endpoint_not_current(self):
  r=extract(self.raw(),'000001','2025-02-03',None);self.assertTrue(all(p['metrics'] is None for p in r['stagePerformance']))
 def test_covered_month(self):
  import datetime as dt
  dates=['2024-12-03','2024-12-20','2025-01-03'];rows=[dict(x=dt.datetime.fromisoformat(d).replace(tzinfo=dt.timezone(dt.timedelta(hours=8))).timestamp()*1000,y=1+i*.1,unitMoney='') for i,d in enumerate(dates)]
  r=extract(self.raw({'Data_netWorthTrend':rows}),'000001','2025-01-03',None);p=r['stagePerformance'][0];self.assertIsNotNone(p['metrics']);self.assertEqual(p['startGapCalendarDays'],0);self.assertIsNone(p['metrics']['annualVolatilityPct']);self.assertFalse(p['frequencyCheck']['dailyAnnualizationAllowed'])
 def test_judgment_does_not_rank_without_peers(self):
  from fund_details import markdown
  text=markdown(extract(self.raw(),'000001','2025-01-03',None));self.assertIn('## 研究结论',text);self.assertIn('暂不能评价',text);self.assertIn('不表示基金表现差',text)
 def test_currency_not_guessed(self):
  from fund_details import markdown
  r=extract(self.raw(),'000001','2025-01-03',None)
  self.assertIsNone(r['facts']['latestNAV']['currency']);self.assertFalse(r['facts']['latestNAV']['currencyVerified']);self.assertIn('币种尚未核实',markdown(r))
 def test_ambiguous_classification_rejected(self):
  for data in [{'categories':['2025-01-01'],'series':[{'name':'股票','data':[90]},{'name':'股票','data':[10]}]}, {'categories':['2025-01-01']*2,'series':[]}, {'categories':{},'series':[]}, {'categories':[],'series':[None]}]:
   with self.subTest(data=data),self.assertRaises(ValueError):extract(self.raw({'Data_assetAllocation':data}),'000001','2025-01-03',None)
 def test_invalid_timestamp(self):
  for stamp in [True,float('nan'),float('inf')]:
   with self.subTest(stamp=stamp),self.assertRaises(ValueError):extract(self.raw({'Data_netWorthTrend':[{'x':stamp,'y':1}]}),'000001','2025-01-03',None)
 def test_empty_snapshot_disclosed(self):
  r=extract(self.raw({'Data_assetAllocation':{'categories':[],'series':[]}}),'000001','2025-01-03',None);self.assertIn('assetAllocation截止日前无可用分类数据',r['gaps'])
if __name__=='__main__':unittest.main()
