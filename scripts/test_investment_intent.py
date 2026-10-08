import unittest,copy
from investment_intent import analyze
class IntentTests(unittest.TestCase):
 def setUp(self):
  self.s={'asOf':'2026-10-05','intent':{'id':'i1','purpose':'教育资金','currency':'CNY','targetDate':'2029-10-05','allowedAssetClasses':['cash','fund'],'minimumCash':10,'maximumAssetWeightPct':80,'maximumStressLossPct':10,'maximumValuationAgeDays':3},'holdings':[{'assetId':'cash:cny','currency':'CNY','marketValue':30,'assetClass':'cash','valuationDate':'2026-10-05'},{'assetId':'fund:example','currency':'CNY','marketValue':70,'assetClass':'fund','valuationDate':'2026-10-05','availableBy':'2026-10-10'}],'cashNeeds':[{'date':'2027-10-05','amount':50}],'scenarios':[{'name':'假设压力','returnShocksPct':{'cash:cny':0,'fund:example':-10}}]}
 def test_supplied_checks_met_not_approval(self):self.assertEqual(analyze(self.s)['status'],'supplied-checks-met')
 def test_cumulative_needs_not_reuse_cash(self):
  self.s['cashNeeds']=[{'date':'2027-10-05','amount':50},{'date':'2028-10-05','amount':50}];self.assertEqual(analyze(self.s)['status'],'constraints-not-met')
 def test_unknown_liquidity_not_zero_or_pass(self):
  del self.s['holdings'][1]['availableBy'];self.assertEqual(analyze(self.s)['status'],'needs-data')
 def test_declared_future_cash_not_used_early(self):
  self.s['holdings'][0]['availableBy']='2028-10-05';self.s['cashNeeds'][0]['amount']=65
  r=analyze(self.s);checks=r['checks']
  self.assertEqual(next(c for c in checks if c['name']=='现金预留')['status'],'fail')
  self.assertEqual(next(c for c in checks if c['name'].startswith('流动性：'))['status'],'fail')
  self.assertEqual(next(c for c in checks if c['name'].startswith('压力后资金覆盖：'))['status'],'fail')
 def test_cash_reserve_failure(self):
  self.s['intent']['minimumCash']=40;self.assertEqual(analyze(self.s)['status'],'constraints-not-met')
 def test_uncovered_stress_unknown(self):
  del self.s['scenarios'][0]['returnShocksPct']['fund:example'];self.assertEqual(analyze(self.s)['status'],'needs-data')
 def test_currency_mismatch_rejects(self):
  self.s['holdings'][1]['currency']='USD'
  with self.assertRaises(ValueError):analyze(self.s)
 def test_future_valuation_rejects(self):
  self.s['holdings'][1]['valuationDate']='2026-10-06'
  with self.assertRaises(ValueError):analyze(self.s)
 def test_duplicate_asset_rejects(self):
  self.s['holdings'].append(copy.deepcopy(self.s['holdings'][0]))
  with self.assertRaises(ValueError):analyze(self.s)
 def test_bool_value_rejects(self):
  self.s['holdings'][0]['marketValue']=True
  with self.assertRaises(ValueError):analyze(self.s)
 def test_pressure_loss_breaches(self):
  self.s['scenarios'][0]['returnShocksPct']['fund:example']=-30;self.assertEqual(analyze(self.s)['status'],'constraints-not-met')
 def test_missing_need_unknown(self):
  self.s['cashNeeds']=[];self.assertEqual(analyze(self.s)['status'],'needs-data')

class BridgeTests(unittest.TestCase):
 def setUp(self):
  base=IntentTests();base.setUp();self.s=base.s;self.s['scenarios']=[]
  self.s['stressCodeMap']={'CASH':'cash:cny','FUND':'fund:example'}
  self.p={'asOf':'2026-10-05','baseCurrency':'CNY','holdings':[{'code':'CASH','currency':'CNY','marketValue':30},{'code':'FUND','currency':'CNY','marketValue':70}],'scenarios':[{'name':'压力','returnShocksPct':{'CASH':0,'FUND':-30}}]}
 def test_recompute_and_check_budget(self):
  from investment_intent import link_portfolio
  r=link_portfolio(self.s,self.p);self.assertEqual(r['status'],'constraints-not-met');self.assertAlmostEqual(r['portfolioLink']['recomputedStressResult']['scenarios'][0]['portfolioReturnPct'],-21)
 def test_old_snapshot_rejected(self):
  from investment_intent import link_portfolio
  self.p['asOf']='2026-10-04'
  with self.assertRaises(ValueError):link_portfolio(self.s,self.p)
 def test_changed_value_rejected(self):
  from investment_intent import link_portfolio
  self.p['holdings'][1]['marketValue']=71
  with self.assertRaises(ValueError):link_portfolio(self.s,self.p)
 def test_mapping_must_be_complete(self):
  from investment_intent import link_portfolio
  del self.s['stressCodeMap']['CASH']
  with self.assertRaises(ValueError):link_portfolio(self.s,self.p)
 def test_existing_scenarios_not_overwritten(self):
  from investment_intent import link_portfolio
  self.s['scenarios']=[{'name':'原情景'}]
  with self.assertRaises(ValueError):link_portfolio(self.s,self.p)
 def test_uncovered_model_scenario_stays_unknown(self):
  from investment_intent import link_portfolio
  del self.p['scenarios'][0]['returnShocksPct']['FUND'];self.assertEqual(link_portfolio(self.s,self.p)['status'],'needs-data')

class FreshnessTests(unittest.TestCase):
 def setUp(self):
  c=IntentTests();c.setUp();self.s=c.s
 def test_stale_snapshot_does_not_pass(self):
  self.s['holdings'][1]['valuationDate']='2026-09-01';r=analyze(self.s);self.assertEqual(r['status'],'needs-data');self.assertEqual(r['holdings'][1]['valuationStatus'],'stale')
 def test_boundary_day_valid(self):
  self.s['holdings'][1]['valuationDate']='2026-10-02';self.assertEqual(analyze(self.s)['status'],'supplied-checks-met')
 def test_missing_freshness_threshold_unknown(self):
  del self.s['intent']['maximumValuationAgeDays'];self.assertEqual(analyze(self.s)['status'],'needs-data')
 def test_bool_threshold_rejected(self):
  self.s['intent']['maximumValuationAgeDays']=True
  with self.assertRaises(ValueError):analyze(self.s)
 def test_negative_threshold_rejected(self):
  self.s['intent']['maximumValuationAgeDays']=-1
  with self.assertRaises(ValueError):analyze(self.s)
 def test_missing_stress_budget_unknown(self):
  del self.s['intent']['maximumStressLossPct'];self.assertEqual(analyze(self.s)['status'],'needs-data')
 def test_stale_cash_still_flagged(self):
  self.s['holdings'][0]['valuationDate']='2026-09-01';self.assertEqual(analyze(self.s)['status'],'needs-data')

class StressLiquidityTests(unittest.TestCase):
 def setUp(self):
  c=IntentTests();c.setUp();self.s=c.s;self.s['cashNeeds'][0]['amount']=85
 def test_loss_budget_passes_but_cash_need_fails(self):
  r=analyze(self.s);self.assertEqual(r['status'],'constraints-not-met');checks=r['checks'];self.assertEqual(next(x for x in checks if x['name'].startswith('压力情景：'))['status'],'pass');self.assertEqual(next(x for x in checks if x['name'].startswith('压力后资金覆盖：'))['status'],'fail')
 def test_missing_liquid_date_stress_unknown(self):
  del self.s['holdings'][1]['availableBy'];r=analyze(self.s);self.assertEqual(next(x for x in r['checks'] if x['name'].startswith('压力后资金覆盖：'))['status'],'unknown')
 def test_cumulative_stress_needs(self):
  self.s['cashNeeds']=[{'date':'2027-10-05','amount':40},{'date':'2028-10-05','amount':45}];r=analyze(self.s);checks=[x for x in r['checks'] if x['name'].startswith('压力后资金覆盖：')];self.assertEqual([x['status'] for x in checks],['pass','fail'])
 def test_delayed_asset_not_counted(self):
  self.s['holdings'][1]['availableBy']='2028-10-05';r=analyze(self.s);self.assertEqual(next(x for x in r['checks'] if x['name'].startswith('压力后资金覆盖：'))['status'],'fail')
 def test_total_loss_not_negative_cash(self):
  self.s['scenarios'][0]['returnShocksPct']['fund:example']=-100;r=analyze(self.s);c=next(x for x in r['checks'] if x['name'].startswith('压力后资金覆盖：'));self.assertIn('可用30.00',c['detail'])

class LiquidationTests(unittest.TestCase):
 def setUp(self):
  c=IntentTests();c.setUp();self.s=c.s;self.s['cashNeeds'][0]['amount']=80
 def outcome(self):return next(x for x in analyze(self.s)['checks'] if x['name'].startswith('压力后资金覆盖：'))
 def test_deduction_after_price_shock(self):
  self.s['scenarios'][0]['liquidationAdjustments']={'fund:example':{'deductionPct':10}};r=self.outcome();self.assertEqual(r['status'],'fail');self.assertIn('可用86.70',r['detail'])
 def test_scenario_delay_overrides_normal_date(self):
  self.s['scenarios'][0]['liquidationAdjustments']={'fund:example':{'availableBy':'2028-10-05'}};self.assertEqual(self.outcome()['status'],'fail')
 def test_unknown_delay_not_normal_date(self):
  self.s['scenarios'][0]['liquidationAdjustments']={'fund:example':{'availableBy':None}};self.assertEqual(self.outcome()['status'],'unknown')
 def test_unknown_asset_rejected(self):
  self.s['scenarios'][0]['liquidationAdjustments']={'other':{'deductionPct':10}}
  with self.assertRaises(ValueError):analyze(self.s)
 def test_invalid_deduction_rejected(self):
  self.s['scenarios'][0]['liquidationAdjustments']={'fund:example':{'deductionPct':101}}
  with self.assertRaises(ValueError):analyze(self.s)
 def test_cash_delay_not_instant(self):
  self.s['scenarios'][0]['liquidationAdjustments']={'cash:cny':{'availableBy':'2028-10-05'}};self.assertEqual(self.outcome()['status'],'fail')
 def test_bridge_liquidity_settings(self):
  from investment_intent import link_portfolio
  c=BridgeTests();c.setUp();c.s['scenarioLiquidity']={'压力':{'fund:example':{'availableBy':None}}};r=link_portfolio(c.s,c.p);self.assertTrue(any('变现日期未明确' in x['detail'] for x in r['checks']))
