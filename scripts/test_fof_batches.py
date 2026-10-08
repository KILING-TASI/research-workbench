import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from fof_reports import run,archive_parser_method,explicit_empty_complete_stock_section,NonEquityScope,both_stock_balance_columns_empty
class Tests(unittest.TestCase):
 def setUp(self):
  gate=patch('pdf_structure_review.review',return_value={'reviewRequired':False});gate.start();self.addCleanup(gate.stop)

 def setup_data(self,d):
  p=Path(d)/'raw.pdf';p.write_bytes(b'%PDF-fixture')
  fof=dict(reportDate='2026-06-30',holdings=[dict(code=c,weight=.1) for c in ['000001','000002','000003']])
  uploads=[dict(code=h['code'],reportDate=fof['reportDate'],path=str(p),title='报告',publishedAt='2026-08-31',sourceUrl='https://example.org/report.pdf') for h in fof['holdings']]
  return fof,uploads
 def parsed(self,weight=.2):return dict(holdings=[dict(securityNamespace='CN-equity',code='600000',weight=weight)])
 def test_resume_only_selected_code(self):
  with tempfile.TemporaryDirectory() as d:
   fof,uploads=self.setup_data(d)
   with patch('fof_reports.inspect_and_parse',return_value=self.parsed()) as parse:
    r=run(fof,d,'2026-10-06',uploads,False,1,1)
   self.assertEqual(set(r['nodes']),{'000002'});self.assertEqual(parse.call_count,1);self.assertEqual(r['batch']['startIndex'],1);self.assertEqual(r['counts']['pending'],2)
 def test_same_method_cannot_replace_different_result(self):
  with tempfile.TemporaryDirectory() as d:
   fof,uploads=self.setup_data(d)
   with patch('fof_reports.inspect_and_parse',return_value=self.parsed()):r=run(fof,d,'2026-10-06',uploads,False,1)
   p=Path(r['rows'][0]['parsedPath']);old=p.read_bytes()
   with patch('fof_reports.inspect_and_parse',return_value=self.parsed(.3)):changed=run(fof,d,'2026-10-06',uploads,False,1)
   self.assertEqual(p.read_bytes(),old);self.assertEqual(changed['counts']['parsed'],0);self.assertIn('同原件同方法结果改变',changed['rows'][0]['reason'])
 def test_method_archive_is_immutable(self):
  with tempfile.TemporaryDirectory() as d:
   sources={'fof_reports.py':b'first','fund_report_holdings.py':b'second'}
   sha=archive_parser_method(d,sources);self.assertEqual(archive_parser_method(d,sources),sha)
   target=Path(d)/'methods'/sha/'fof_reports.py';self.assertEqual(target.read_bytes(),b'first')
   target.write_bytes(b'changed')
   with self.assertRaisesRegex(ValueError,'档案内容改变'):archive_parser_method(d,sources)
 def test_empty_stock_section_has_exact_scope(self):
  heading='7.3 期末按公允价值占基金资产净值比例大小排序的所有股票投资明细'
  self.assertTrue(explicit_empty_complete_stock_section(heading+'\n无。\n7.4 报告期内股票投资组合的重大变动'))
  self.assertFalse(explicit_empty_complete_stock_section(heading+'\n1 600000 股票 100 20.00 1.00\n无。\n7.4 报告期内股票投资组合的重大变动'))
  self.assertFalse(explicit_empty_complete_stock_section(heading+'\n无。\n8.4 报告期内股票投资组合的重大变动'))
  self.assertFalse(explicit_empty_complete_stock_section('7.3 前十名股票投资明细\n无。\n7.4 报告期内股票投资组合的重大变动'))
 def test_no_stock_scope_not_zero_node(self):
  with tempfile.TemporaryDirectory() as d:
   fof,uploads=self.setup_data(d)
   with patch('fof_reports.inspect_and_parse',side_effect=NonEquityScope(40)):r=run(fof,d,'2026-10-06',uploads,False,1)
   self.assertEqual(r['counts']['parsed'],0);self.assertEqual(r['nodes'],{});self.assertEqual(r['rows'][0]['scopeStatus'],'non-equity-analysis-required');self.assertEqual(r['rows'][0]['noStockDisclosurePage'],40)
 def test_empty_balance_requires_two_disclosed_amount_columns(self):
  self.assertTrue(both_stock_balance_columns_empty(['其中：股票投资',None,'-','-']))
  self.assertTrue(both_stock_balance_columns_empty(['其中：股票投资','6.4.7.2','－','－']))
  self.assertFalse(both_stock_balance_columns_empty(['其中：股票投资',None,'-',None]))
  self.assertFalse(both_stock_balance_columns_empty(['其中：股票投资',None,'-','100.00']))
 def test_source_warning_keeps_parsed_amounts_but_no_node(self):
  with tempfile.TemporaryDirectory() as d:
   fof,uploads=self.setup_data(d)
   with patch('pdf_structure_review.review',return_value={'reviewRequired':True,'warnings':['fixture-warning']}),patch('fof_reports.inspect_and_parse',return_value=self.parsed()):r=run(fof,d,'2026-10-06',uploads,False,1)
   self.assertEqual(r['nodes'],{});self.assertEqual(r['rows'][0]['scopeStatus'],'source-structure-review-required');self.assertTrue(Path(r['rows'][0]['parsedPath']).exists())
 def test_bad_start_index_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   fof,uploads=self.setup_data(d)
   for start in [-1,True,4]:
    with self.subTest(start=start),self.assertRaises(ValueError):run(fof,d,'2026-10-06',uploads,False,1,start)
if __name__=='__main__':unittest.main()
