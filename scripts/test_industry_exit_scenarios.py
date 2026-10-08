import unittest,tempfile
from pathlib import Path
from industry_exit_scenarios import supply,concentration,exit_cash,run,scenario_judgment
from company_scenarios import value,load_json
A=lambda v:dict(value=v,basis='assumption',note='验收假设')
class Tests(unittest.TestCase):
 def test_supply_missing_input_withholds_full_balance_judgment(self):
  s=self.supply_input();s['periods'][0]['imports']=None
  text=''.join(scenario_judgment('supply',supply(s)))
  self.assertIn('不能形成完整供需平衡判断',text);self.assertNotIn('未显示需求超过',text)
 def test_partial_market_is_not_a_full_market_rating(self):
  text=''.join(scenario_judgment('concentration',concentration(self.concentration_input())))
  self.assertIn('50.00%',text);self.assertIn('不能给出精确的全市场集中度',text)
 def test_exit_missing_costs_is_not_final_net_return(self):
  s=self.exit_input();s['scenarios'][0]['costCoverage']='partial'
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'report';r=run('exit',s,p);text=(p/'研究情景.md').read_text(encoding='utf-8')
   self.assertLess(text.index('## 先看判断'),text.index('## 退出现金流情景'))
   self.assertIn('不能当作最终净收益',text);self.assertIsNone(r['scenarios'][0]['xirrPct'])
 def test_compact_dates_rejected_across_modes(self):
  s=self.supply_input();s['asOf']='20261005'
  with self.assertRaisesRegex(ValueError,'日期'):supply(s)
  s=self.supply_input();s['periods'][0]['start']='20250101'
  with self.assertRaisesRegex(ValueError,'日期'):supply(s)
  s=self.concentration_input();s['period']='20251231'
  with self.assertRaisesRegex(ValueError,'日期'):concentration(s)
  s=self.exit_input();s['scenarios'][0]['flows'][0]['date']='20250101'
  with self.assertRaisesRegex(ValueError,'日期'):exit_cash(s)
 def test_source_value_rejects_credentials_and_invalid_url(self):
  base=dict(value=1,basis='source-statement',note='来源陈述',publishedAt='2026-01-01',locator='PDF第1页')
  for source in ['https://user:secret@example.org/a','https:///a','https://example.org:bad/a','https://example.org/ a']:
   with self.subTest(source=source),self.assertRaises(ValueError):value({**base,'sourceUrl':source},'2026-10-05')
  self.assertEqual(value({**base,'sourceUrl':'https://example.org/a'},'2026-10-05'),1)
 def test_json_duplicate_or_overflow_not_silent(self):
  for text in ['{"amount":1,"amount":2}','{"amount":1e999}']:
   with self.subTest(text=text),self.assertRaises(ValueError):load_json(text)
 def industry(self):return dict(name='验收',scope='同一产品同一市场',unit='吨',asOf='2026-10-05')
 def supply_input(self):return dict(self.industry(),periods=[dict(start='2025-01-01',end='2025-12-31',openingInventory=A(10),production=A(100),imports=A(5),exports=A(15),demand=A(90),closingInventory=A(10))])
 def test_supply_reconcile(self):self.assertEqual(supply(self.supply_input())['periods'][0]['balanceDifference'],0)
 def test_missing_imports_not_zero(self):
  s=self.supply_input();s['periods'][0]['imports']=None;self.assertIsNone(supply(s)['periods'][0]['projectedClosingInventory'])
 def test_shortage_not_negative_actual_stock(self):
  s=self.supply_input();s['periods'][0]['demand']=A(110);r=supply(s)['periods'][0];self.assertEqual(r['supplyDeficit'],10);self.assertTrue(r['alerts'])
 def test_mixed_units(self):
  s=self.supply_input();s['periods'][0]['imports']['unit']='万吨'
  with self.assertRaises(ValueError):supply(s)
 def concentration_input(self):return dict(self.industry(),period='2025-12-31',marketTotal=A(100),universeComplete=False,firms=[dict(id='a',name='a',volume=A(30)),dict(id='b',name='b',volume=A(20))])
 def test_partial_not_renormalized(self):
  r=concentration(self.concentration_input());self.assertEqual(r['knownCoverage'],.5);self.assertEqual(r['metrics']['HHI']['lower'],1300);self.assertEqual(r['metrics']['HHI']['upper'],3800);self.assertIsNone(r['metrics']['CR3']['exact'])
 def test_full_universe_needs_total(self):
  s=self.concentration_input();s['universeComplete']=True
  with self.assertRaises(ValueError):concentration(s)
 def test_company_exceeds_total(self):
  s=self.concentration_input();s['firms'][1]['volume']=A(80)
  with self.assertRaises(ValueError):concentration(s)
 def exit_input(self):return dict(identity=dict(name='验收'),currency='CNY',unit='元',asOf='2026-10-05',scenarios=[dict(name='同日期出口',costCoverage='declared-complete',cashFlowCoverage='declared-complete',flows=[dict(date='2025-01-01',kind='investment',amount=A(100)),dict(date='2026-01-01',kind='proceeds',amount=A(110)),dict(date='2026-01-01',kind='fee',amount=A(1)),dict(date='2026-01-01',kind='tax',amount=A(0))])])
 def test_exit_cost_and_dates(self):
  r=exit_cash(self.exit_input())['scenarios'][0];self.assertEqual(r['knownCashChange'],9);self.assertAlmostEqual(r['netRecoveryMultiple'],1.09);self.assertAlmostEqual(r['xirrPct'],9.0064,places=2)
 def test_partial_cost_no_net_or_xirr(self):
  s=self.exit_input();s['scenarios'][0]['costCoverage']='partial';r=exit_cash(s)['scenarios'][0];self.assertIsNone(r['netRecoveryMultiple']);self.assertIsNone(r['xirrPct'])
 def test_missing_fee_not_zero(self):
  s=self.exit_input();s['scenarios'][0]['flows']=[x for x in s['scenarios'][0]['flows'] if x['kind']!='fee']
  with self.assertRaises(ValueError):exit_cash(s)
 def test_multiple_sign_changes_no_xirr(self):
  s=self.exit_input();s['scenarios'][0]['flows'].append(dict(date='2026-01-02',kind='fee',amount=A(1)));r=exit_cash(s)['scenarios'][0];self.assertIsNone(r['xirrPct']);self.assertEqual(r['knownCashChange'],8)
 def test_partial_cashflow_blocks_annualization(self):
  s=self.exit_input();s['scenarios'][0]['cashFlowCoverage']='partial';r=exit_cash(s)['scenarios'][0];self.assertIsNone(r['xirrPct']);self.assertIsNone(r['netRecoveryMultiple'])
 def test_report_explains_actual_gap_only(self):
  s=self.exit_input();s['scenarios'][0]['cashFlowCoverage']='partial'
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'report';run('exit',s,p);text=(p/'研究情景.md').read_text(encoding='utf8');self.assertIn('现金流或费用税收尚未完整',text);self.assertNotIn('同日或无可求根',text)
if __name__=='__main__':unittest.main()
