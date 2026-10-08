import unittest,tempfile,hashlib
from pathlib import Path
from company_scenarios import dcf,forecast,relative,wacc,numeric_bindings,input_evidence_summary
A=lambda v:dict(value=v,basis='assumption',note='测试假设')
class Tests(unittest.TestCase):
 def spec(self):return dict(asOf='2026-10-05',identity=dict(name='测试'),currency='CNY',unit='元')
 def dcf_input(self):return dict(self.spec(),discountRate=A(.1),terminalGrowth=A(0),netDebt=A(0),cashFlows=[dict(A(100),year=1),dict(A(100),year=2)])
 def test_dcf_constant_perpetuity(self):self.assertAlmostEqual(dcf(self.dcf_input())['base']['enterpriseValue'],1000)
 def test_fcfe_rejected(self):
  s=self.dcf_input();s['cashFlowType']='FCFE'
  with self.assertRaises(ValueError):dcf(s)
  s=self.dcf_input();s['cashFlows'][0]['cashFlowType']='FCFE'
  with self.assertRaises(ValueError):dcf(s)
 def test_numeric_anchor_and_mutation(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'raw.json';p.write_text('{"items":[{"a/b":1000000}]}');s=self.dcf_input()
   s['sourceFiles']=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())]
   s['netDebt']=dict(value=1,basis='source-statement',note='百万元',sourceUrl='https://example.org/report',locator='底稿',publishedAt='2026-01-01',numericBinding=dict(path=str(p),pointer='/items/0/a~1b',scale=.000001))
   self.assertFalse(numeric_bindings(s)[0]['originalVerified']);dcf(s)
   s['netDebt']['value']=2
   with self.assertRaises(ValueError):dcf(s)
 def test_assumption_cannot_bind(self):
  s=self.dcf_input();s['netDebt']['numericBinding']={}
  with self.assertRaises(ValueError):dcf(s)
 def test_evidence_does_not_promote_numeric_anchor(self):
  s=self.dcf_input();s['netDebt']=dict(value=1,basis='source-statement',note='陈述',numericBinding={'pointer':'/amount'})
  r=input_evidence_summary(s);self.assertEqual(r['sourceClaimCount'],1);self.assertGreater(r['assumptionCount'],0)
  e=next(e for e in r['entries'] if e['inputPath']=='/netDebt');self.assertTrue(e['numericAnchorDeclared']);self.assertFalse(e['originalVerified'])
 def test_unified_scenario_preserves_missing_type(self):
  import json
  from research_workflow import context,run_scenario_review
  with tempfile.TemporaryDirectory() as d:
   base=Path(d);ctx=context(dict(sessionId='scenario-test',baseCurrency='CNY',frequency='monthly',dividendTreatment='reinvest',asOf='2026-10-05',benchmark=None,riskFreeRate=0,annualization=12,missingData='fail',timezone='Asia/Shanghai'))
   (base/'context.json').write_text(json.dumps(ctx));(base/'input.json').write_text(json.dumps(self.dcf_input()))
   m=dict(contextPath=str(base/'context.json'),inputPath=str(base/'input.json'),template='company-scenario-review',mode='dcf',outDir=str(base/'output'))
   r=run_scenario_review(m);self.assertEqual(r['status'],'scenario-calculated-with-gaps');self.assertEqual(len(r['gaps']),1)
   s=self.dcf_input();s['cashFlowType']='FCFF';(base/'input.json').write_text(json.dumps(s));m['outDir']=str(base/'explicit')
   self.assertEqual(run_scenario_review(m)['status'],'scenario-calculated')
 def test_wacc_tax_weights(self):self.assertAlmostEqual(wacc(dict(equityCost=A(.1),debtCost=A(.05),taxRate=A(.2),equityWeight=A(.6)),'2026-10-05'),.076)
 def test_invalid_terminal(self):
  s=self.dcf_input();s['terminalGrowth']=A(.1)
  with self.assertRaises(ValueError):dcf(s)
 def test_per_share_unit(self):
  s=self.dcf_input();s['shares']=dict(A(100),unitScale='百万元')
  with self.assertRaises(ValueError):dcf(s)
 def forecast_input(self):
  b=dict(revenue=100,cash=100,receivables=0,inventory=0,fixedAssets=100,otherAssets=0,payables=0,debt=0,otherLiabilities=0,equity=200)
  a=dict(revenueGrowth=0,grossMargin=.5,opexRate=0,taxRate=0,depreciationRate=.1,capexRate=.1,DSO=0,DIO=0,DPO=0,interestRate=0,netBorrowing=0,payoutRate=.5)
  return dict(self.spec(),opening={k:A(v) for k,v in b.items()},years=[dict(year=i,**{k:A(v) for k,v in a.items()}) for i in [1,2,3]])
 def test_three_statements_reconcile(self):
  r=forecast(self.forecast_input());self.assertTrue(all(abs(y['balanceDifference'])<1e-8 for y in r['years']));self.assertAlmostEqual(r['years'][0]['income']['netProfit'],40);self.assertAlmostEqual(r['years'][0]['cashflow']['netChange'],20)
 def test_funding_gap_stops(self):
  s=self.forecast_input();s['years'][0]['capexRate']=A(1);s['opening']['cash']=A(0);s['opening']['equity']=A(100);r=forecast(s);self.assertEqual(r['years'][0]['status'],'unfunded-cash-deficit');self.assertEqual(r['uncomputedYears'],[2,3])
 def test_opening_not_balanced(self):
  s=self.forecast_input();s['opening']['equity']=A(999)
  with self.assertRaises(ValueError):forecast(s)
 def test_repayment_exceeds_debt(self):
  s=self.forecast_input();s['years'][0]['netBorrowing']=A(-1)
  with self.assertRaises(ValueError):forecast(s)
 def relative_input(self):
  return dict(self.spec(),companies=[dict(code=id,name=id,valuationDate='2026-10-01',financialPeriod='2025-12-31',definition='FY2025',marketCap=A(1000),netProfit=A(profit),equity=A(500),revenue=A(2000)) for id,profit in [('a',100),('b',-100)]])
 def test_negative_profit_no_pe(self):self.assertIsNone(relative(self.relative_input())['rows'][1]['multiples']['PE'])
 def test_missing_market_cap_not_guessed(self):
  s=self.relative_input();s['companies'][0]['marketCap']=None;r=relative(s);self.assertIsNone(r['rows'][0]['multiples']['PE']);self.assertIn('marketCap',r['rows'][0]['gaps'])
 def test_missing_market_cap_note_does_not_split_table(self):
  from company_scenarios import run
  with tempfile.TemporaryDirectory() as d:
   s=self.relative_input();s['companies'][0]['marketCap']=None
   out=Path(d)/'report';run('relative',s,out)
   text=(out/'经营与估值情景.html').read_text('utf-8')
   self.assertNotIn('<p>|',text)
   self.assertIn('市值未取得',text)
 def test_relative_period_mismatch(self):
  s=self.relative_input();s['companies'][1]['financialPeriod']='2025-06-30'
  with self.assertRaises(ValueError):relative(s)
 def test_source_mutation(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'raw';p.write_text('new');s=self.dcf_input();s['sourceFiles']=[dict(path=str(p),sha256=hashlib.sha256(b'old').hexdigest())]
   with self.assertRaises(ValueError):dcf(s)
 def test_source_response_status_not_security_code(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'raw.json';p.write_text('{"code":0,"data":{}}');s=self.dcf_input();s['identity']['code']='600031';s['sourceFiles']=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())];dcf(s)
 def test_numeric_security_identity_conflict_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'raw.json';p.write_text('{"code":600032}');s=self.dcf_input();s['identity']['code']='600031';s['sourceFiles']=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())]
   with self.assertRaises(ValueError):dcf(s)
class ReadableSensitivityTests(unittest.TestCase):
 dcf_input=Tests.dcf_input
 spec=Tests.spec
 def test_sensitivity_invalid_cells_and_negative_equity_readable(self):
  from company_scenarios import run
  s=self.dcf_input();s['discountRate']=A(.01);s['terminalGrowth']=A(.009);s['netDebt']=A(1000000);s['shares']=dict(A(100),unitScale='元')
  with tempfile.TemporaryDirectory() as d:
   r=run('dcf',s,Path(d)/'report');md=(Path(d)/'report/经营与估值情景.md').read_text(encoding='utf-8')
   self.assertIn('每股股权情景值',md);self.assertIn('不足以覆盖净债务',md);self.assertIn('未计算项',md)
   self.assertEqual(md.count('|未计算|未计算|'),sum(c['status']=='invalid' for c in r['sensitivity']))
class EvidenceReportTests(unittest.TestCase):
 def test_all_assumptions_not_presented_as_verified_history(self):
  from company_scenarios import run
  s=Tests().dcf_input()
  with tempfile.TemporaryDirectory() as d:
   r=run('dcf',s,Path(d)/'report');md=(Path(d)/'report/经营与估值情景.md').read_text(encoding='utf-8')
   self.assertIn('全部为假设',md);self.assertIn('没有执行公告原文核验',md);self.assertEqual(r['inputEvidenceSummary']['sourceClaimCount'],0)
 def test_evidence_metadata_preserved(self):
  s=Tests().dcf_input();s['netDebt']=dict(value=2,basis='calculation',note='债务减现金',sourceUrl='https://example.org',locator='期末字段',publishedAt='2026-01-01')
  e=next(x for x in input_evidence_summary(s)['entries'] if x['basis']=='calculation')
  self.assertEqual(e['publishedAt'],'2026-01-01');self.assertEqual(e['locator'],'期末字段');self.assertFalse(e['originalVerified'])
class BoundPeriodTests(unittest.TestCase):
 def test_actual_source_date_overrides_backdated_input(self):
  import json
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'rows.json';p.write_text(json.dumps(dict(rows=[dict(period='2026-06-30',publishedAt='2026-08-25',raw=dict(amount=1))])))
   s=Tests().dcf_input();s['sourceFiles']=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())];s['netDebt']=dict(value=1,basis='source-statement',note='历史字段',sourceUrl='https://example.org',locator='行',publishedAt='2026-08-25',numericBinding=dict(path=str(p),pointer='/rows/0/raw/amount'))
   self.assertEqual(numeric_bindings(s)[0]['boundPeriod'],'2026-06-30')
   s['netDebt']['publishedAt']='2026-01-01'
   with self.assertRaisesRegex(ValueError,'发布日期与绑定'):numeric_bindings(s)
   s['netDebt']['publishedAt']='2026-08-25';s['asOf']='2026-08-01'
   with self.assertRaisesRegex(ValueError,'晚于研究截止'):numeric_bindings(s)
   s['asOf']='2026-10-05';s['netDebt']['observationPeriod']='2025-12-31'
   with self.assertRaisesRegex(ValueError,'报告期与绑定'):numeric_bindings(s)

class ForecastScopeTests(unittest.TestCase):
 def test_financial_declarations_rejected(self):
  from company_scenarios import forecast_scope
  for category in ['bank','insurance','securities','financial']:
   with self.assertRaisesRegex(ValueError,'不适用'):forecast_scope(dict(companyType=category))
  self.assertEqual(forecast_scope({})['status'],'financial-type-not-detected-not-independent-verified')
 def test_bank_source_cannot_be_overridden_by_declaration(self):
  import json
  from company_scenarios import forecast_scope
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'source.json';p.write_text(json.dumps(dict(tables=dict(balance=dict(rows=[dict(raw=dict(ORG_TYPE='银行'))])))))
   with self.assertRaisesRegex(ValueError,'底稿标识'):forecast_scope(dict(companyType='nonfinancial',sourceFiles=[dict(path=str(p))]))

class ScenarioInputSafetyTests(unittest.TestCase):
 spec=Tests.spec
 dcf_input=Tests.dcf_input
 forecast_input=Tests.forecast_input
 def test_duplicate_and_nonfinite_json_rejected(self):
  from company_scenarios import load_json
  for text in ['{"value":1,"value":2}','{"value":NaN}']:
   with self.assertRaises(ValueError):load_json(text)
 def test_boolean_year_not_integer(self):
  s=self.dcf_input();s['cashFlows'][0]['year']=True
  with self.assertRaises(ValueError):dcf(s)
  s=self.forecast_input();s['years'][0]['year']=True
  with self.assertRaises(ValueError):forecast(s)
 def test_compact_cutoff_rejected(self):
  s=self.dcf_input();s['asOf']='20261005'
  with self.assertRaises(ValueError):dcf(s)
 def test_note_requires_text(self):
  s=self.dcf_input();s['netDebt']['note']=['not text']
  with self.assertRaises(ValueError):dcf(s)
 def test_render_failure_no_success_result(self):
  from unittest.mock import patch
  from company_scenarios import run
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'output'
   with patch('company_scenarios.render',side_effect=ValueError('render failed')):
    with self.assertRaises(ValueError):run('dcf',self.dcf_input(),out)
   self.assertFalse((out/'result.json').exists())

class ScenarioJudgmentTests(unittest.TestCase):
 spec=Tests.spec
 dcf_input=Tests.dcf_input
 forecast_input=Tests.forecast_input
 def test_negative_equity_is_not_negative_market_price(self):
  from company_scenarios import scenario_judgment
  s=self.dcf_input();s['netDebt']=A(2000)
  text=''.join(scenario_judgment('dcf',dcf(s)))
  self.assertIn('不足以覆盖',text);self.assertIn('不是置信区间',text)
 def test_funding_gap_explanation_does_not_claim_feasibility(self):
  from company_scenarios import scenario_judgment
  s=self.forecast_input();s['years'][0]['capexRate']=A(1);s['opening']['cash']=A(0);s['opening']['equity']=A(100)
  text=''.join(scenario_judgment('forecast',forecast(s)))
  self.assertIn('第1年',text);self.assertIn('未计算年份当作零',text)
 def test_no_deficit_is_not_solvency_certificate(self):
  from company_scenarios import scenario_judgment
  self.assertIn('不证明现实偿债安全',''.join(scenario_judgment('forecast',forecast(self.forecast_input()))))
 def test_relative_coverage_respects_missing_and_negative_profit(self):
  from company_scenarios import scenario_judgment
  r=dict(rows=[dict(multiples=dict(PE=None,PB=2,PS=3,EV_EBITDA=None)),dict(multiples=dict(PE=10,PB=1,PS=None,EV_EBITDA=4))])
  text=''.join(scenario_judgment('relative',r))
  self.assertIn('PE 1/2',text);self.assertIn('PB 2/2',text);self.assertIn('不能仅凭',text)
 def test_report_leads_with_judgment_before_numbers(self):
  from company_scenarios import run
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'report';run('dcf',self.dcf_input(),out)
   text=(out/'经营与估值情景.md').read_text(encoding='utf-8')
   self.assertLess(text.index('## 先看结论'),text.index('## 折现情景'))

class DebtScopeTests(unittest.TestCase):
 forecast_input=Tests.forecast_input
 spec=Tests.spec
 def test_missing_scope_does_not_certify_full_debt(self):
  self.assertEqual(forecast(self.forecast_input())['debtScopeReview']['status'],'not-declared')
 def test_components_sum_and_exclusions_kept(self):
  s=self.forecast_input();s['debtScope']=dict(components=[dict(A(0),name='借款')],excluded=['租赁负债'])
  r=forecast(s)['debtScopeReview'];self.assertEqual(r['excluded'],['租赁负债']);self.assertEqual(r['status'],'declared-components-matched-not-complete')
 def test_mismatched_sum_rejected(self):
  s=self.forecast_input();s['debtScope']=dict(components=[dict(A(1),name='借款')])
  with self.assertRaisesRegex(ValueError,'不一致'):forecast(s)
 def test_duplicate_and_excluded_conflict_rejected(self):
  for scope in [dict(components=[dict(A(0),name='借款'),dict(A(0),name='借款')]),dict(components=[dict(A(0),name='借款')],excluded=['借款'])]:
   s=self.forecast_input();s['debtScope']=scope
   with self.assertRaisesRegex(ValueError,'冲突'):forecast(s)

if __name__=='__main__':unittest.main()
