import unittest,tempfile,json
from pathlib import Path
from industry_financials import value,change,analyze_company,summarize_companies,markdown

def archive():
 rows=[]
 for period,v in [('2025-03-31',10),('2025-06-30',30),('2026-03-31',15),('2026-06-30',40)]:
  rows.append(dict(period=period,publishedAt=period,currency='CNY',raw=dict(SECURITY_CODE='600519',SECUCODE='600519.SH',ORG_TYPE='general',OPERATE_INCOME=v,OPERATE_COST=v/2,NETPROFIT=v/3,ACCOUNTS_RECE=v)))
 return dict(code='600519',asOf='2026-10-05',tables={k:dict(rows=[dict(r,raw=dict(r['raw'])) for r in rows],sources=[]) for k in ['income','balance','cashflow']})
class FinancialSectorTests(unittest.TestCase):
 def test_cumulative_money_subtraction_preserves_disclosed_cents(self):
  a=archive()
  for row in a['tables']['income']['rows']:
   if row['period']=='2026-06-30':row['raw']['OPERATE_INCOME']=27767190529.75
   if row['period']=='2026-03-31':row['raw']['OPERATE_INCOME']=9564242921.53
  self.assertEqual(value(a,'revenue','2026-06-30')['value'],18202947608.22)
 def test_gross_payment_reversal_is_not_negative_quarter_spend(self):
  for sign in (1,-1):
   a=archive()
   for row in a['tables']['cashflow']['rows']:
    row['raw']['CONSTRUCT_LONG_ASSET']=sign*(100 if row['period']=='2026-03-31' else 80)
    row['raw']['NETCASH_OPERATE']=100 if row['period']=='2026-03-31' else 80
   v=value(a,'capex','2026-06-30');self.assertIsNone(v['value']);self.assertEqual(v['cumulativeDifference'],-20*sign)
   self.assertIn('不能直接还原',v['reason'])
   self.assertEqual(value(a,'operatingCash','2026-06-30')['value'],-20)
   for row in a['tables']['cashflow']['rows']:
    if row['period']=='2026-06-30':row['raw']['CONSTRUCT_LONG_ASSET']=sign*150
   self.assertEqual(value(a,'capex','2026-06-30')['value'],sign*50)
 def test_cash_transitions_are_not_profit_or_loss(self):
  self.assertEqual(change(-30,10,'operatingCash')['reason'],'由净流入转净流出')
  self.assertEqual(change(30,-10,'operatingCash'),dict(value=None,reason='由净流出转净流入'))
  self.assertEqual(change(-5,-10,'operatingCash')['reason'],'净流出收窄')
  self.assertEqual(change(-20,-10,'operatingCash')['reason'],'净流出扩大')
  self.assertEqual(change(-20,10,'parentProfit')['reason'],'转亏')
  self.assertEqual(change(-5,-10,'financeExpense')['reason'],'负值绝对值减少')
 def test_report_distinguishes_inapplicability_and_missing(self):
  from industry_financials import applicability_notes
  c=analyze_company(archive(),dict(scope='consolidated',currency='CNY',unit='元',classificationVersion='v1',sectorType='financial'),'2026-06-30')
  text=''.join(applicability_notes(c))
  for phrase in ['不适用，不是取数失败','未取得仍逐项保留缺失','净利润率不等于银行净息差','资产负债率不等于资本充足率']:self.assertIn(phrase,text)
  c['metadata']['sectorType']='general';self.assertEqual(applicability_notes(c),[])
 def test_source_bank_cannot_use_general_group(self):
  a=archive()
  for t in a['tables'].values():
   for row in t['rows']:row['raw']['ORG_TYPE']='银行'
  m=dict(scope='consolidated',currency='CNY',unit='元',classificationVersion='user-v1',sectorType='general')
  with self.assertRaisesRegex(ValueError,'金融企业'):analyze_company(a,m,'2026-06-30')
  m['sectorType']='financial';c=analyze_company(a,m,'2026-06-30')
  for key in ['grossMargin','expenseRatio','cashProfit','capexIntensity']:self.assertIsNone(c['ratios'][key])
  self.assertIn('资本充足率',c['signals'][0])
 def test_inapplicability_not_counted_as_missing(self):
  m=dict(group='金融样本',scope='consolidated',currency='CNY',unit='元',classificationVersion='v1',sectorType='financial')
  c=analyze_company(archive(),m,'2026-06-30');groups=summarize_companies([c])
  for key in ['grossMargin','expenseRatio','cashProfit','capexIntensity']:
   self.assertEqual(groups[0]['ratios'][key]['missingCount'],0)
   self.assertEqual(groups[0]['ratios'][key]['notApplicableCount'],1)
  text=markdown(dict(period='2026-06-30',companies=[c],groups=groups,coverage=dict(requested=1,analyzed=1),limitations=[],failures=[]))
  self.assertIn('毛利率中位数 不适用；有效0家，缺失0家，不适用1家',text)
 def test_group_ratio_display_has_explicit_units(self):
  m=dict(group='样本',scope='consolidated',currency='CNY',unit='元',classificationVersion='v1',sectorType='general')
  c=analyze_company(archive(),m,'2026-06-30');c['ratios']['cashProfit']=1.2
  text=markdown(dict(period='2026-06-30',companies=[c],groups=summarize_companies([c]),coverage=dict(requested=1,analyzed=1),limitations=[],failures=[]))
  self.assertIn('毛利率中位数 50.00%',text)
  self.assertIn('经营现金流与净利润之比中位数 1.20倍',text)
 def test_observation_explains_growth_without_inventing_causes(self):
  from industry_financials import company_observation
  meta=dict(group='样本',scope='consolidated',currency='CNY',unit='元',classificationVersion='v1',sectorType='general')
  c=analyze_company(archive(),meta,'2026-06-30');c['metrics']['revenue']['yoy']['value']=.2;c['metrics']['parentProfit']['yoy']['value']=.05;c['metrics']['operatingCash']['current']['value']=-1
  text=company_observation(c);self.assertIn('尚未等幅',text);self.assertIn('不直接认定财务危机',text)
  c['metrics']['operatingCash']['current']['value']=0
  self.assertIn('净额为零',company_observation(c));self.assertNotIn('本季度经营现金净流入',company_observation(c))
  c['metadata']['sectorType']='financial';self.assertIn('净息差',company_observation(c));self.assertNotIn('尚未等幅',company_observation(c))
 def test_future_type_does_not_control_current_research(self):
  a=archive();a['tables']['income']['rows'].append(dict(period='2026-09-30',publishedAt='2026-10-31',currency='CNY',raw=dict(SECURITY_CODE='600519',ORG_TYPE='银行')))
  m=dict(scope='consolidated',currency='CNY',unit='元',classificationVersion='user-v1',sectorType='general')
  self.assertIsNotNone(analyze_company(a,m,'2026-06-30')['ratios']['grossMargin'])
class Tests(unittest.TestCase):
 def test_unresolved_unit_is_calculation_gap(self):
  from industry_financials import metadata_unit_warnings
  meta=dict(scope='consolidated',currency='CNY',unit='渠道原单位（待原文确认）',classificationVersion='test')
  c=analyze_company(archive(),meta,'2026-06-30')
  self.assertIn(metadata_unit_warnings(meta)[0],c['gaps'])
  meta['unit']='元';self.assertEqual(metadata_unit_warnings(meta),[])
 def test_quarter_and_stock(self):
  a=archive();self.assertEqual(value(a,'revenue','2026-06-30')['value'],25);self.assertEqual(value(a,'receivables','2026-06-30')['value'],40)
 def test_missing_and_conflict(self):
  a=archive();a['tables']['income']['rows']=[r for r in a['tables']['income']['rows'] if r['period']!='2026-03-31'];self.assertIsNone(value(a,'revenue','2026-06-30')['value'])
  a=archive();r=dict(a['tables']['income']['rows'][-1]);r['raw']=dict(r['raw'],OPERATE_INCOME=50);a['tables']['income']['rows'].append(r);self.assertIsNone(value(a,'revenue','2026-06-30')['value'])
 def test_negative_to_zero_described_by_metric_not_generic_loss(self):
  self.assertEqual(change(0,-10,'operatingCash'),dict(value=None,reason='净流出归零'))
  self.assertEqual(change(0,-10,'parentProfit'),dict(value=None,reason='亏损归零'))
  self.assertEqual(change(0,-10,'financeExpense'),dict(value=None,reason='负值归零'))
  self.assertEqual(change(10,0,'parentProfit'),dict(value=None,reason='基数为零'))
 def test_negative_base(self):
  self.assertIsNone(change(5,-5)['value']);self.assertEqual(change(5,-5)['reason'],'转盈');self.assertEqual(change(-5,-10)['reason'],'亏损收窄');self.assertEqual(change(-5,5)['value'],-2)
 def test_income_basis_warning_requires_available_distinct_values(self):
  from financial_source_binding import income_basis_warnings
  a=archive();self.assertEqual(income_basis_warnings(a,'2026-06-30'),[])
  row=a['tables']['income']['rows'][-1]['raw'];row['TOTAL_OPERATE_INCOME']=45
  self.assertEqual(income_basis_warnings(a,'2026-06-30')[0]['operatingIncome'],40)
  row['TOTAL_OPERATE_INCOME']=40;self.assertEqual(income_basis_warnings(a,'2026-06-30'),[])
 def test_scope_currency_and_bank(self):
  m=dict(scope='consolidated',currency='CNY',unit='元',classificationVersion='user-v1',sectorType='financial')
  r=analyze_company(archive(),m,'2026-06-30');self.assertIsNone(r['ratios']['grossMargin'])
  with self.assertRaises(ValueError):analyze_company(archive(),dict(m,currency='USD'),'2026-06-30')
  with self.assertRaises(ValueError):analyze_company(archive(),dict(m,scope=None),'2026-06-30')
 def test_batch_bad_archive_keeps_requested_scope_and_good_result(self):
  from industry_financials import run
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory);good=p/'good.json';bad=p/'bad.json';good.write_text(json.dumps(archive()),encoding='utf-8');bad.write_text('{"code":"600031","x":1e999}',encoding='utf-8')
   meta=dict(group='样本',scope='consolidated',currency='CNY',unit='元',classificationVersion='v1',sectorType='general')
   r=run(dict(period='2026-06-30',companies=[dict(archive=str(good),metadata=meta),dict(code='600031',archive=str(bad),metadata=meta)]),p/'out')
   self.assertEqual(r['coverage']['requested'],2);self.assertEqual(r['coverage']['analyzed'],1)
   self.assertEqual(len(r['failures']),1);self.assertEqual(r['failures'][0]['code'],'600031')
   self.assertIn('资料读取失败',r['failures'][0]['reason'])
 def test_period_comparison_quarter_stock_and_missing(self):
  from industry_financials import period_comparison
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);a=p/'archive.json';a.write_text(json.dumps(archive()),encoding='utf8')
   m=dict(scope='consolidated',currency='CNY',unit='元',classificationVersion='user-v1',sectorType='general')
   s=dict(beforePeriod='2026-03-31',period='2026-06-30',companies=[dict(archive=str(a),metadata=m)])
   r=period_comparison(s,p/'out');rows={x['metric']:x for x in r['companies'][0]['metrics']}
   self.assertEqual(rows['revenue']['difference'],10);self.assertEqual(rows['receivables']['difference'],25);self.assertIsNone(rows['operatingCash']['difference'])
   s['beforePeriod']=s['period']
   with self.assertRaisesRegex(ValueError,'递增'):period_comparison(s,p/'bad')
if __name__=='__main__':unittest.main()
