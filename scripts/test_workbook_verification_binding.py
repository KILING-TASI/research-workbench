import unittest,tempfile,json,hashlib
from pathlib import Path
from unittest.mock import patch
from financial_workbook_inputs import verified_commentary_checks
class Tests(unittest.TestCase):
 def test_pending_questions_cannot_be_hidden_from_gap_list(self):
  from financial_workbook_inputs import verify_commentary_coverage
  financial=dict(coverage=dict(requested=1),failures=[],companies=[dict(code='600900',gaps=[])])
  saved=dict(coverage=financial['coverage'],failures=[],companies=[dict(code='600900',gaps=[],interpretations=[dict(followUp=['核对收款时点'])])])
  with self.assertRaisesRegex(ValueError,'待核实问题'):verify_commentary_coverage(saved,financial)
  saved['companies'][0]['gaps']=['待核实问题：核对收款时点']
  self.assertEqual(verify_commentary_coverage(saved,financial),'financial-coverage-and-gaps-matched')
 def case(self,path):
  spec={};hashes={}
  for key in ['financialResult','originalResult']:
   p=path/(key+'.json');p.write_text('{}',encoding='utf8');spec[key]=str(p);hashes[key]=hashlib.sha256(p.read_bytes()).hexdigest()
  saved=dict(period='2026-06-30',inputHashes=hashes,companies=[dict(code='600900',checks=[dict(status='matched')],reportHash='pdfhash')]);p=path/'commentary.json';spec['commentaryResult']=str(p)
  return spec,saved,p
 def run_case(self,spec):
  return verified_commentary_checks(spec,dict(period='2026-06-30',companies=[dict(code='600900')]),dict(companies=[dict(code='600900',fileSha256='pdfhash')]),{'600900':{}})
 @patch('company_financial_report.original_checks',return_value=[dict(status='matched')])
 def test_changed_status_rejected(self,m):
  with tempfile.TemporaryDirectory() as d:
   spec,saved,p=self.case(Path(d));saved['companies'][0]['checks'][0]['status']='missing';p.write_text(json.dumps(saved),encoding='utf8')
   with self.assertRaisesRegex(ValueError,'重新核对'):self.run_case(spec)
 @patch('company_financial_report.original_checks',return_value=[dict(status='matched')])
 def test_comparative_status_tampering_rejected(self,m):
  with tempfile.TemporaryDirectory() as d:
   spec,saved,p=self.case(Path(d));saved['companies'][0]['comparativeChecks']=[dict(status='difference')];p.write_text(json.dumps(saved),encoding='utf8')
   with self.assertRaisesRegex(ValueError,'比较列'):self.run_case(spec)
 def test_changed_input_hash_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   spec,saved,p=self.case(Path(d));p.write_text(json.dumps(saved),encoding='utf8');Path(spec['financialResult']).write_text('{"changed":true}')
   with self.assertRaisesRegex(ValueError,'输入'):self.run_case(spec)
 @patch('company_financial_report.original_checks',return_value=[dict(status='matched')])
 def test_valid_saved_checks_accepted(self,m):
  with tempfile.TemporaryDirectory() as d:
   spec,saved,p=self.case(Path(d));p.write_text(json.dumps(saved),encoding='utf8');self.assertEqual(len(self.run_case(spec)),1)
 @patch('company_financial_report.original_checks',return_value=[dict(status='matched')])
 def test_added_unbound_interpretation_rejected(self,m):
  with tempfile.TemporaryDirectory() as d:
   spec,saved,p=self.case(Path(d));saved['companies'][0]['interpretations']=[dict(text='已证明竞争优势',basis='company-statement',evidence=[])]
   p.write_text(json.dumps(saved),encoding='utf8')
   with self.assertRaisesRegex(ValueError,'可解析原文'):self.run_case(spec)
 def test_coverage_tamper_and_hidden_missing_field_rejected(self):
  from financial_workbook_inputs import verify_commentary_coverage
  financial=dict(coverage=dict(requested=2,analyzed=1),failures=[dict(code='000001',reason='缺失')],companies=[dict(code='600900',gaps=['研发费用缺失'])])
  saved=dict(coverage=financial['coverage'],failures=financial['failures'],companies=[dict(code='600900',gaps=['研发费用缺失'])])
  self.assertEqual(verify_commentary_coverage(saved,financial),'financial-coverage-and-gaps-matched')
  for changed in [dict(saved,coverage=dict(requested=1,analyzed=1)),dict(saved,failures=[]),dict(saved,companies=[dict(code='600900',gaps=[])])]:
   with self.assertRaises(ValueError):verify_commentary_coverage(changed,financial)
  self.assertEqual(verify_commentary_coverage({},financial),'legacy-coverage-not-recorded')

class WorkbookInputSnapshotTests(unittest.TestCase):
 def test_quarter_review_in_commentary_cannot_be_dropped_or_changed(self):
  from financial_workbook_inputs import verify_quarter_alignment
  q=dict(code='600900',fields=[{'status':'matched'}]);commentary=[dict(code='600900',quarterOriginalChecks=q)]
  with self.assertRaisesRegex(ValueError,'不能静默丢弃'):verify_quarter_alignment(commentary,[])
  with self.assertRaisesRegex(ValueError,'不一致'):verify_quarter_alignment(commentary,[dict(q,fields=[{'status':'not-verified'}])])
  verify_quarter_alignment(commentary,[q]);verify_quarter_alignment([dict(code='600900')],[])
 def test_json_duplicate_or_nonfinite_not_silent(self):
  from financial_workbook_inputs import load_json
  for text in ['{"period":1,"period":2}','{"amount":NaN}','{"amount":1e999}','[]']:
   with self.assertRaises(ValueError):load_json(text)
 def test_associated_file_changed_during_prepare_rejected(self):
  from financial_workbook_inputs import prepare
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);fin=root/'f.json';original=root/'o.json'
   fin.write_text(json.dumps(dict(period='2026-06-30',companies=[],groups=[],limitations=[])),encoding='utf-8')
   original.write_text('{"companies":[]}',encoding='utf-8')
   def mutate(*args):original.write_text('{"companies":[],"changed":true}',encoding='utf-8')
   with patch('financial_workbook_inputs.bound_originals'),patch('financial_workbook_inputs.bound_archives',return_value=({},{})),patch('financial_workbook_inputs.verify_financial_snapshot',side_effect=mutate):
    with self.assertRaisesRegex(ValueError,'准备期间'):prepare(dict(financialResult=str(fin),originalResult=str(original),archives=[]))

class LimitationScopeTests(unittest.TestCase):
 def test_collection_boundary_not_report_missing_claim(self):
  from financial_workbook_inputs import financial_stage_limitations
  s=dict(limitations=['未自动获取公告正文，经营原因和未来展望不由数字推断','其他缺口'])
  r=financial_stage_limitations(s)
  self.assertIn('计算阶段',r[0]);self.assertIn('本次原文取得和核验状态',r[0]);self.assertEqual(r[1],'其他缺口')
  self.assertEqual(s['limitations'][0],'未自动获取公告正文，经营原因和未来展望不由数字推断')

if __name__=='__main__':unittest.main()
