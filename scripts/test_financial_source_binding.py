import unittest,tempfile,json,hashlib
from pathlib import Path
from unittest.mock import patch
from financial_source_binding import bound_archives,bound_originals
class Tests(unittest.TestCase):
 def test_mutation_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'archive.json';p.write_text('{"code":"600309"}');f=dict(companies=[dict(code='600309',archiveSha256=hashlib.sha256(p.read_bytes()).hexdigest())]);bound_archives(f,[p]);p.write_text('{"code":"600309","changed":true}')
   with self.assertRaises(ValueError):bound_archives(f,[p])
 def test_duplicate_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'archive.json';p.write_text('{"code":"600309"}')
   with self.assertRaises(ValueError):bound_archives(dict(companies=[]),[p,p])
 def test_missing_rejected(self):
  with self.assertRaises(ValueError):bound_archives(dict(companies=[dict(code='600309')]),[])
 @patch('research_report_reading.verify_pdf_pages',return_value='pdf-reparsed-pages-matched')
 def test_pdf_mutation_rejected(self,mock_verify):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'600309').mkdir();pdf=p/'600309/report.pdf';pdf.write_bytes(b'%PDF-original');s=dict(companies=[dict(code='600309',parseStatus='parsed',fileSha256=hashlib.sha256(pdf.read_bytes()).hexdigest())]);self.assertEqual(len(bound_originals(s,p/'result.json')),1);pdf.write_bytes(b'%PDF-changed')
   with self.assertRaises(ValueError):bound_originals(s,p/'result.json')
 @patch('research_report_reading.verify_pdf_pages',side_effect=ValueError('保存的页码文字不一致'))
 def test_saved_text_failure_propagates(self,mock_verify):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'600309').mkdir();pdf=p/'600309/report.pdf';pdf.write_bytes(b'%PDF-original')
   pages=[dict(page=1,text='保存的原文文字')]
   source=dict(companies=[dict(code='600309',parseStatus='parsed',fileSha256=hashlib.sha256(pdf.read_bytes()).hexdigest(),pages=pages)])
   with self.assertRaisesRegex(ValueError,'页码文字'):bound_originals(source,p/'result.json')
   self.assertEqual(mock_verify.call_args.args[0]['pages'],pages)
   self.assertEqual(mock_verify.call_args.args[0]['parser'],'pdfplumber')
 def test_recalculation_rejects_saved_metric(self):
  from financial_source_binding import verify_financial_snapshot
  rebuilt=dict(code='600031',period='2026-06-30',metrics={'revenue':1},ratios={},signals=[],gaps=[],sourceUrls={})
  saved=dict(rebuilt,metadata={},metrics={'revenue':99})
  with patch('industry_financials.analyze_company',return_value=rebuilt):
   with self.assertRaisesRegex(ValueError,'metrics'):verify_financial_snapshot(dict(period='2026-06-30',companies=[saved]),{'600031':{}})
 def test_recalculation_rejects_group_snapshot(self):
  from financial_source_binding import verify_financial_snapshot
  rebuilt=dict(code='600031',period='2026-06-30',metrics={},ratios={},signals=[],gaps=[],sourceUrls={})
  saved=dict(rebuilt,metadata={})
  with patch('industry_financials.analyze_company',return_value=rebuilt),patch('industry_financials.summarize_companies',return_value=[{'sampleSize':1}]):
   with self.assertRaisesRegex(ValueError,'分组快照'):verify_financial_snapshot(dict(period='2026-06-30',companies=[saved],groups=[{'sampleSize':2}]),{'600031':{}})
 def test_disclosed_restated_comparatives_flagged(self):
  from financial_source_binding import comparability_warnings
  report=dict(parseStatus='parsed',pages=[dict(page=7,text='公司于2025年发生同一控制下的企业合并，本报告期公司对比较期间财务数据进行相应追溯调整。')])
  self.assertEqual(comparability_warnings(report)[0]['page'],7)
 def test_generic_accounting_policy_not_current_restatement(self):
  from financial_source_binding import comparability_warnings
  self.assertEqual(comparability_warnings(dict(parseStatus='parsed',pages=[dict(page=100,text='同一控制下合并按照规定进行追溯调整。')])),[])

class AdjustedColumnTests(unittest.TestCase):
 def test_late_note_other_scope_change_retained(self):
  from financial_source_binding import comparability_warnings
  text='5、其他原因的合并范围变动\n说明新设、清算等事项\n√适用 □不适用\n本集团注销一家子公司。'
  result=comparability_warnings({'parseStatus':'parsed','pages':[{'page':174,'text':text}]})
  self.assertEqual(result[0]['page'],174)
  self.assertEqual(result[0]['kind'],'other-consolidation-scope-change-disclosed')
  self.assertIn('注销',result[0]['excerpt'])
 def test_inactive_or_generic_scope_note_not_active_change(self):
  from financial_source_binding import comparability_warnings
  for text in ['其他原因的合并范围变动 □适用 √不适用','会计政策：合并范围变动包括注销等事项。']:
   self.assertEqual(comparability_warnings({'parseStatus':'parsed','pages':[{'page':174,'text':text}]}),[])
 def test_actual_comparative_headers_warn(self):
  from financial_source_binding import comparability_warnings
  r={'parseStatus':'parsed','pages':[{'page':9,'text':'主要会计数据\n上年同期 本报告期\n调整后 调整前\n营业收入 100 90 80'}]}
  warning=comparability_warnings(r)[0]
  self.assertEqual(warning['page'],9);self.assertEqual(warning['kind'],'comparative-adjusted-columns-disclosed')
 def test_generic_adjustment_discussion_not_table_warning(self):
  from financial_source_binding import comparability_warnings
  for text in ['会计政策调整前与调整后，上年同期需复核。','主要会计数据 上年同期 营业收入 100 90']:
   self.assertEqual(comparability_warnings({'parseStatus':'parsed','pages':[{'page':9,'text':text}]}),[])

class FinancialShapeTests(unittest.TestCase):
 def test_duplicate_company_cannot_double_count(self):
  from financial_source_binding import bound_archives
  with self.assertRaisesRegex(ValueError,'重复'):bound_archives(dict(companies=[dict(code='600000'),dict(code='600000')]),[])
 def test_wrong_path_list_rejected(self):
  from financial_source_binding import bound_archives
  with self.assertRaisesRegex(ValueError,'列表'):bound_archives(dict(companies=[]),'archive.json')
 def test_duplicate_json_fields_rejected(self):
  import tempfile
  from pathlib import Path
  from financial_source_binding import bound_archives
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'a.json';p.write_text('{"code":"600000","code":"600001"}')
   with self.assertRaises(ValueError):bound_archives(dict(companies=[]),[p])

if __name__=='__main__':unittest.main()
