import unittest,tempfile,hashlib
from pathlib import Path
from fund_report_archive import manager_name_evidence,identity,run,scope_notes,top_fund_rows,report_markdown
class Tests(unittest.TestCase):
 def test_adjacent_share_codes_keep_original_token_boundaries(self):
  from unittest.mock import patch
  from types import SimpleNamespace
  class Page:
   def __init__(self,text):self.text=text
   def extract_text(self):return self.text
  class Document:
   def __init__(self,codes):self.pages=[Page('示例基金2026年中期报告 2026年6月30日 送出日期2026年8月29日'),Page('下属分级交易代码\n'+codes)]
   def __enter__(self):return self
   def __exit__(self,*args):pass
  meta=dict(title='示例基金2026年中期报告',publishedAt='2026-08-29')
  with patch('fund_report_archive.pdf_module',return_value=SimpleNamespace(open=lambda p:Document('001247 002091'))):
   self.assertIn('匹配',identity('sample.pdf','002091','2026-06-30',meta)['identityStatus'])
  with patch('fund_report_archive.pdf_module',return_value=SimpleNamespace(open=lambda p:Document('001247002091'))):
   with self.assertRaisesRegex(ValueError,'未确认基金代码'):identity('sample.pdf','002091','2026-06-30',meta)
 def test_help_without_site_packages(self):
  import subprocess,sys
  script=Path(__file__).with_name('fund_report_archive.py')
  result=subprocess.run([sys.executable,'-B','-S',str(script),'--help'],capture_output=True,text=True,encoding='utf-8')
  self.assertEqual(result.returncode,0,result.stderr)
  self.assertIn('--period',result.stdout)
 def test_missing_pdf_support_fails_before_output(self):
  import subprocess,sys,os
  script=Path(__file__).with_name('fund_report_archive.py')
  with tempfile.TemporaryDirectory() as directory:
   output=Path(directory)/'archive'
   result=subprocess.run([sys.executable,'-B','-S',str(script),'--code','001156','--period','2026-06-30','--as-of','2026-10-07','--out-dir',str(output)],capture_output=True,text=True,encoding='utf-8',env=dict(os.environ,PYTHONIOENCODING='utf-8'))
   self.assertEqual(result.returncode,2)
   self.assertIn('pdfplumber',result.stderr)
   self.assertNotIn('Traceback',result.stderr)
   self.assertFalse(output.exists())
 def test_substitution_note_retained_without_adjustment_amount(self):
  notes=scope_notes([(40,'注：上表中的权益投资含可退替代款估值增值。')])
  self.assertEqual(notes[0]['kind'],'refundable-substitution-valuation-scope');self.assertIsNone(notes[0]['adjustmentAmountCNY']);self.assertEqual(notes[0]['page'],40)
 def test_human_brief_shows_note_without_full_reconciliation(self):
  r=dict(metadata=self.meta(),status='会计差额待核验',reportDate='2026-06-30',sha256='abc',gaps=['差额未解释'],portfolioScopeEvidence=scope_notes([(40,'上表中的权益投资含可退替代款估值增值。')]))
  text=report_markdown(r);self.assertIn('PDF第40页',text);self.assertIn('不能据此认定',text);self.assertIn('https://example.org/report.pdf',text)
 def test_relative_output_saves_absolute_document_path(self):
  import os
  old=Path.cwd()
  with tempfile.TemporaryDirectory() as t:
   try:
    os.chdir(t);r=run('110022','2025-12-31','2026-10-03',Path('archive'),False,self.meta,lambda u:b'%PDF-test',lambda *a:dict(identityStatus='匹配'))
    self.assertTrue(Path(r['documentPath']).is_absolute());os.chdir(old);self.assertTrue(Path(r['documentPath']).is_file())
   finally:os.chdir(old)
 def test_empty_direct_equity_scope_not_total_risk_zero(self):
  notes=scope_notes([(59,'8.4 期末按公允价值占基金资产净值比例大小排序的所有权益投资明细\n本基金本报告期末未持有股票及存托凭证。')]);self.assertEqual(notes[0]['kind'],'no-direct-equity');self.assertIn('不说明',notes[0]['meaning'])
 def test_toc_not_empty_equity_evidence(self):
  self.assertFalse(scope_notes([(3,'8.4 期末按公允价值排序的所有权益投资明细 .... 59')]))
 def fund_document(self,rank='1',value='10.00',ending='投资组合报告附注'):
  class Table:
   bbox=(0,20,100,40)
   def extract(self):return [['序号','基金名称','基金类型','运作方式','管理人','公允价值','比例'],[rank,'某ETF','股票型','开放式','某公司',value,'5.00']]
  class Page:
   def extract_text(self):return "金额单位：人民币元"
   def search(self,pattern):
    import re
    text='8.10 期末按公允价值占基金资产净值比例大小排序的前十名基金投资明细\n8.11 '+ending
    return [dict(top=10 if '.10' in pattern else 50)] if re.search(pattern,text) else []
   def find_tables(self):return [Table()]
  class Doc:pages=[Page()]
  return Doc()
 def test_domestic_futures_section_ends_fund_table(self):
  for ending in ['报告期末本基金投资股指期货的交易情况说明','本基金投资股指期货的投资政策']:
   self.assertEqual(len(top_fund_rows(self.fund_document(ending=ending))['rows']),1)
 def test_unknown_next_section_not_assumed(self):
  with self.assertRaises(ValueError):top_fund_rows(self.fund_document(ending='其他未知章节'))
 def test_top_funds_not_complete_or_identified(self):
  r=top_fund_rows(self.fund_document());self.assertFalse(r['complete']);self.assertFalse(r['accountingTotalVerified']);self.assertIsNone(r['rows'][0]['code']);self.assertEqual(r['rows'][0]['reportedWeightPct'],'5.00')
 def test_top_funds_reject_rank_gap_and_bad_amount(self):
  for rank,value in [('2','10'),('1','NaN')]:
   with self.subTest(rank=rank,value=value),self.assertRaises(ValueError):top_fund_rows(self.fund_document(rank,value))
 def meta(self,*a):return dict(title='报告',publishedAt='2026-03-31',sourceUrl='https://example.org/report.pdf')
 def test_parse_failure_keeps_report(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'r';r=run('110022','2025-12-31','2026-10-03',p,True,self.meta,lambda u:b'%PDF-test',lambda *a:dict(identityStatus='匹配'),lambda *a:(_ for _ in ()).throw(ValueError('布局不支持')));self.assertTrue((p/'report.pdf').exists());self.assertIsNone(r['holdings']);self.assertTrue(any('解析未完成' in x for x in r['gaps']))
 def test_unresolved_accounting_is_not_full_success(self):
  with tempfile.TemporaryDirectory() as t:
   r=run('110022','2025-12-31','2026-10-03',Path(t)/'r',True,self.meta,lambda u:b'%PDF-test',lambda *a:dict(identityStatus='匹配'),lambda *a:{**self.valid_holdings(), 'accountingReconciliation':dict(status='unresolved')})
   self.assertIn('会计差额待核验',r['status'])
   self.assertIsNotNone(r['holdings'])
   self.assertTrue(any('暂不进入' in x for x in r['gaps']))
 def valid_holdings(self):
  return dict(id='110022',reportDate='2025-12-31',publishedAt=self.meta()['publishedAt'],sourceUrl=self.meta()['sourceUrl'],sourceSha256=hashlib.sha256(b'%PDF-test').hexdigest(),disclosureScope='completeEquity',holdings=[{'code':'600000','weight':.1}])
 def test_invalid_parse_result_never_marks_completed(self):
  invalid=[None,{},[],{**self.valid_holdings(),'id':'000001'},{**self.valid_holdings(),'sourceSha256':'wrong'},{**self.valid_holdings(),'holdings':[]},{**self.valid_holdings(),'accountingReconciliation':None}]
  for parsed in invalid:
   with self.subTest(parsed=parsed),tempfile.TemporaryDirectory() as t:
    r=run('110022','2025-12-31','2026-10-03',Path(t)/'r',True,self.meta,lambda u:b'%PDF-test',lambda *a:dict(identityStatus='匹配'),lambda *a:parsed)
    self.assertEqual(r['status'],'副本身份已匹配');self.assertIsNone(r['holdings']);self.assertTrue(any('股票持仓解析未完成' in x for x in r['gaps']))
 def test_nonpdf_no_output(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'r'
   with self.assertRaises(ValueError):run('110022','2025-12-31','2026-10-03',p,False,self.meta,lambda u:b'HTML')
   self.assertFalse(p.exists())
 def test_future_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaises(ValueError):run('110022','2025-12-31','2026-01-01',Path(t)/'r',False,self.meta)
 def test_blank_title_or_code_rejected_before_file_access(self):
  for code,title in [('110022',' '),('.*','报告')]:
   with self.assertRaisesRegex(ValueError,'身份不明确'):identity('missing.pdf',code,'2025-12-31',{'title':title,'publishedAt':'2026-03-31'})
 def test_invalid_thousand_group_not_silently_stripped(self):
  with self.assertRaisesRegex(ValueError,'格式无效'):top_fund_rows(self.fund_document(value='1,0.00'))
 def test_manager_name_requires_label_and_unique_name(self):
  pages=[(1,'基金管理人：南方基金管理股份有限公司'),(4,'基金管理人名称 南方基金管理股份有限公司')]
  r=manager_name_evidence(pages);self.assertEqual(r['name'],'南方基金管理股份有限公司');self.assertEqual(len(r['records']),2)
  self.assertEqual(manager_name_evidence([(1,'经理观点提到南方基金管理股份有限公司')])['status'],'missing')
  self.assertEqual(manager_name_evidence(pages+[(5,'基金管理人：其他基金管理有限公司')])['status'],'conflict')
if __name__=='__main__':unittest.main()
