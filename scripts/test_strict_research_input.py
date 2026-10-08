import unittest,tempfile
from pathlib import Path
from research_pipeline import read,review,collect
class StrictResearchInput(unittest.TestCase):
 def test_etf_replacement_uses_shared_fee_and_date_gates(self):
  import importlib.util
  from unittest.mock import patch
  import replacement_research
  path=Path(__file__).resolve().parents[1]/'modules/etf-sector-rotation/scripts/replacement_research.py'
  spec=importlib.util.spec_from_file_location('topic_replacement_test',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  product=lambda code,fee:dict(code=code,currency='CNY',annualFeePct=dict(value=fee,observedAt='2026-10-01',availableAt='2026-10-01',sourceUrl='https://example.org/fees',locator='费用',verification='official-reviewed'))
  data=dict(asOf='2026-10-08',current=product('510300',.6),candidate=product('510310',.2),positionCurrency='CNY',positionValue=100000,holdingYears=3)
  with patch.object(replacement_research,'evaluate_layers',return_value={}),patch.object(module._module,'evaluate_layers',return_value={}):
   self.assertEqual(module.evaluate(data),replacement_research.evaluate(data));self.assertIsNone(module.evaluate(data)['annualFeeSaving'])
  with self.assertRaises(ValueError):module.evaluate({**data,'asOf':'20261008'})
 def test_project_universe_cannot_silently_replace_identity(self):
  import json
  from unittest.mock import patch
  for rows in [[{'code':'000991','name':'first'},{'code':'000991','name':'second'}],{},[{'code':True}],[{'code':'991'}]]:
   with self.subTest(rows=rows),tempfile.TemporaryDirectory() as root:
    assets=Path(root)/'outputs/fund-market/assets';assets.mkdir(parents=True)
    (assets/'data.json').write_text(json.dumps({'rows':rows}),encoding='utf-8')
    (assets/'detail-data.json').write_text(json.dumps({'funds':{}}),encoding='utf-8')
    with patch('portable_collect.collect') as fallback,self.assertRaisesRegex(ValueError,'项目标的库'):collect(root,'fund',['000991'],'2026-10-08',False)
    fallback.assert_not_called()
 def test_evidence_rejects_bool_page_and_credentials(self):
  from research_pipeline import evidence
  record=dict(securityCode='000991',field='value',value=1,unit='元',currency='CNY',period='2026-06-30',publishedAt='2026-08-30',statementScope='fund',periodBasis='half-year',sourceUrl='https://example.org/report.pdf',documentPath='missing.pdf',page=1,excerpt='value',reviewer='AI')
  with self.assertRaisesRegex(ValueError,'页码'):evidence({**record,'page':True})
  with self.assertRaisesRegex(ValueError,'HTTPS'):evidence({**record,'sourceUrl':'https://user:password@example.org/report.pdf'})
 def test_etf_topic_uses_shared_cache_identity_gate(self):
  import importlib.util,json
  path=Path(__file__).resolve().parents[1]/'modules/etf-sector-rotation/scripts/portable_collect.py'
  spec=importlib.util.spec_from_file_location('topic_cache_test',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  with tempfile.TemporaryDirectory() as root:
   p=Path(root)/'research-data/etf/510880.json';p.parent.mkdir(parents=True)
   p.write_text(json.dumps({'code':'999999','kind':'etf','history':[]}),encoding='utf-8');before=p.read_bytes()
   result=module.collect(root,'etf',['510880'],'2026-10-08',False)
   self.assertEqual(result['rows'][0]['code'],'510880');self.assertTrue(result['rows'][0]['errors'])
   self.assertEqual(p.read_bytes(),before)
 def test_workflow_reader_rejects_duplicate_and_nonfinite_values(self):
  from research_workflow import load
  for text in ['{"nav":1,"nav":2}','{"value":NaN}','{"value":1e999}']:
   with self.subTest(text=text),tempfile.TemporaryDirectory() as root:
    p=Path(root)/'input.json';p.write_text(text,encoding='utf-8')
    with self.assertRaises(ValueError):load(p)
 def test_workflow_duplicate_fund_rows_not_silently_overwritten(self):
  import json
  from research_workflow import context,run_fund_comparison
  with tempfile.TemporaryDirectory() as root:
   folder=Path(root);ctx=context(dict(sessionId='teaching',baseCurrency='CNY',frequency='trading_day',dividendTreatment='reinvest',asOf='2026-10-08',benchmark=None,riskFreeRate=0,annualization=252,missingData='common_dates',timezone='Asia/Shanghai'))
   cp=folder/'context.json';cp.write_text(json.dumps(ctx),encoding='utf-8')
   bp=folder/'bundle.json';bp.write_text(json.dumps({'asOf':'2026-10-08','rows':[{'kind':'fund','code':'000991'},{'kind':'fund','code':'000991'},{'kind':'fund','code':'006228'}]}),encoding='utf-8')
   with self.assertRaisesRegex(ValueError,'身份重复'):run_fund_comparison({'template':'fund-comparison','contextPath':str(cp),'bundlePath':str(bp),'codes':['000991','006228'],'comparisonGroup':'教学'},folder)
 def test_duplicate_top_or_nested_fields_rejected(self):
  for text in ['{"asOf":"2026-09-30","asOf":"2026-09-01"}','{"rows":[{"nav":1,"nav":2}]}']:
   with self.subTest(text=text),tempfile.TemporaryDirectory() as root:
    p=Path(root)/'input.json';p.write_text(text,'utf-8')
    with self.assertRaisesRegex(ValueError,'重复字段'):read(p)
 def test_nonfinite_json_rejected(self):
  for value in ['NaN','Infinity','-Infinity','1e999','-1e999']:
   with self.subTest(value=value),tempfile.TemporaryDirectory() as root:
    p=Path(root)/'input.json';p.write_text('{"value":'+value+'}','utf-8')
    with self.assertRaises(ValueError):read(p)
 def test_valid_bom_input_kept(self):
  with tempfile.TemporaryDirectory() as root:
   p=Path(root)/'input.json';p.write_text('{"value":1,"missing":null}','utf-8-sig');self.assertEqual(read(p),{'value':1,'missing':None})
 def test_review_duplicate_identity_never_silently_hides_change(self):
  before={'type':'sample','rows':[{'code':'000991','value':1},{'code':'000991','value':2}]}
  after={'type':'sample','rows':[{'code':'000991','value':9},{'code':'000991','value':2}]}
  with self.assertRaisesRegex(ValueError,'身份重复'):review(before,after)
 def test_review_unique_identity_reordering_is_not_a_change(self):
  before={'type':'sample','rows':[{'code':'000991','value':1},{'code':'006228','value':2}]}
  after={'type':'sample','rows':list(reversed(before['rows']))}
  self.assertEqual(review(before,after)['changes'],[])
 def test_review_index_and_explicit_identity_collision_rejected(self):
  value={'type':'sample','rows':[1,{'id':'0','value':2}]}
  with self.assertRaisesRegex(ValueError,'身份重复'):review(value,value)
 def test_project_unknown_fund_uses_standalone_without_losing_known_rows(self):
  import json
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as root:
   assets=Path(root)/'outputs/fund-market/assets';assets.mkdir(parents=True)
   (assets/'data.json').write_text(json.dumps({'rows':[{'code':'000991','name':'教学旧库基金'}]}),'utf-8')
   (assets/'detail-data.json').write_text(json.dumps({'funds':{'000991':{'history':[{'date':'2026-09-30','nav':1.2}]}}}),'utf-8')
   fallback={'type':'research-bundle','rows':[{'code':'003095','kind':'fund','history':[],'gaps':['教学未取得资料']}], 'mode':'standalone'}
   with patch('portable_collect.collect',return_value=fallback) as mocked:
    result=collect(root,'fund',['003095','000991'],'2026-10-08',False)
   mocked.assert_called_once_with(Path(root).resolve(),'fund',['003095'],'2026-10-08',False)
   self.assertEqual([r['code'] for r in result['rows']],['003095','000991'])
   self.assertEqual(result['rows'][1]['history'][0]['nav'],1.2)
   self.assertEqual(result['rows'][0]['gaps'],['教学未取得资料'])
   self.assertEqual(result['mode'],'project-with-standalone-fallback')
