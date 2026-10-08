import unittest,tempfile,json,hashlib
from pathlib import Path
from unittest.mock import patch
from research_report_reading import language,check_entry,build
class LanguageProfileTests(unittest.TestCase):
 def test_english_appendix_not_hidden_by_chinese_body(self):
  from research_report_reading import language_profile
  pages=[dict(page=1,text='财务分析经营状况'*100),dict(page=2,text='Financial assumptions and risk '*20),dict(page=3,text='123456')]
  p=language_profile(pages)
  self.assertEqual(p['overall'],'Chinese-or-mixed')
  self.assertEqual(p['pagesByLanguage']['English-dominant'],[2])
  self.assertEqual(p['pagesByLanguage']['undetermined'],[3])
class Tests(unittest.TestCase):
 @patch('research_report_reading.verify_pdf_pages',return_value='pdf-reparsed-pages-matched')
 def test_benchmark_review_states_and_scope(self,m):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);pdf=p/'original.pdf';pdf.write_bytes(b'original');r=self.report();r.update(pdfPath=str(pdf),sha256=hashlib.sha256(pdf.read_bytes()).hexdigest())
   r['pages'].append(dict(page=2,text='业绩比较基准 本基金无业绩比较基准。'))
   archive=p/'archive.json';archive.write_text(json.dumps(dict(asOf='2026-10-05',reports=[r])),encoding='utf8')
   e=dict(text='解释',evidence=[dict(page=1,quote='这是原文披露的完整证据')]);a=dict(reportId='a',logic=[e],assumptions=[e],depth=[e],benchmarkReview=True)
   result=build(dict(archive=str(archive),analyses=[a]),p/'out')['analyses'][0]
   self.assertEqual(result['benchmarkReview']['status'],'explicitly-not-defined');self.assertEqual(result['citationScope']['citedPages'],[1,2]);self.assertFalse(any('未找到基准' in g for g in result['gaps']))
   self.assertIn('报告明确说明未设',(p/'out/研报精读.md').read_text(encoding='utf8'))
   a['benchmarkReview']='true'
   with self.assertRaisesRegex(ValueError,'布尔值'):build(dict(archive=str(archive),analyses=[a]),p/'bad')
 def report(self):return dict(id='a',title='测试报告',status='readable',sha256='x',pages=[dict(page=1,text='这是原文披露的完整证据。')])
 def test_duplicate_page_rejects_quote(self):
  r=self.report();r['pages'].append(dict(r['pages'][0]));e=dict(text='解释',evidence=[dict(page=1,quote='这是原文披露的完整证据')])
  with self.assertRaisesRegex(ValueError,'物理页重复'):check_entry(e,r)
 def test_duplicate_archive_id_rejected_before_pdf_read(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);a=p/'a.json';a.write_text(json.dumps(dict(asOf='2026-10-05',reports=[self.report(),self.report()])),encoding='utf8')
   with self.assertRaisesRegex(ValueError,'ID重复'):build(dict(archive=str(a),analyses=[]),p/'out')
   self.assertFalse((p/'out').exists())
 def test_language_content(self):
  self.assertEqual(language('Annual report financial growth '*20),'English-dominant')
  self.assertEqual(language('财务分析经营状况'*20),'Chinese-or-mixed')
 def test_quote_requires_correct_page(self):
  r=self.report();e=dict(text='解释',evidence=[dict(page=1,quote='这是原文披露的完整证据')]);self.assertEqual(check_entry(e,r)['evidence'][0]['status'],'quote-located')
  e['evidence'][0]['page']=2
  with self.assertRaises(ValueError):check_entry(e,r)
 def test_unsupported_quote(self):
  with self.assertRaises(ValueError):check_entry(dict(text='解释',evidence=[dict(page=1,quote='并不存在的虚构证据')]),self.report())
 def test_hash_change_blocks_build(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);pdf=p/'original.pdf';pdf.write_bytes(b'changed');r=self.report();r['pdfPath']=str(pdf);a=p/'archive.json';a.write_text(json.dumps(dict(asOf='2026-10-05',reports=[r])),encoding='utf8')
   with self.assertRaises(ValueError):build(dict(archive=str(a),analyses=[dict(reportId='a')]),p/'out')
 @patch('research_report_reading.verify_pdf_pages',return_value='pdf-reparsed-pages-matched')
 def test_cross_report_origin_not_consensus(self,mock_verify):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);pdf=p/'original.pdf';pdf.write_bytes(b'original');rs=[]
   for id in ['a','b','c']:
    r=self.report();r.update(id=id,pdfPath=str(pdf),sha256=hashlib.sha256(b'original').hexdigest(),originGroup='same');rs.append(r)
   a=p/'archive.json';a.write_text(json.dumps(dict(asOf='2026-10-05',reports=rs)),encoding='utf8');e=dict(text='解释',evidence=[dict(page=1,quote='这是原文披露的完整证据')]);analyses=[dict(reportId=id,logic=[e],assumptions=[e],depth=[e]) for id in ['a','b','c']]
   row=dict(reportIds=['a','b'],kind='agreement',text='同源观点重复',evidence=[dict(reportId=id,page=1,quote='这是原文披露的完整证据') for id in ['a','b']])
   row['underlyingSources']={'a':['shared-data'],'b':['shared-data']}
   r=build(dict(archive=str(a),analyses=analyses,comparisons=[row]),p/'out');self.assertEqual(r['comparisons'][0]['underlyingSourceAssessment']['sharedDeclaredSources'],['shared-data']);self.assertIn('共同登记来源',(p/'out/研报精读.md').read_text(encoding='utf8')); self.assertEqual(mock_verify.call_count,3);self.assertEqual(r['unreadReports'],[]);self.assertIn('a 第1页',(p/'out/研报精读.md').read_text(encoding='utf8'));self.assertFalse(r['comparisons'][0]['distinctDeclaredOrigins']);self.assertEqual((p/'out/sources/report-1.pdf').read_bytes(),b'original');self.assertIn('sources/report-1.pdf#page=1',(p/'out/研报精读.md').read_text(encoding='utf8'));self.assertEqual(r['sourceFiles'][0]['sha256'],hashlib.sha256(b'original').hexdigest())
 def test_saved_text_tamper_rejected(self):
  from research_report_reading import verify_pdf_pages
  from types import SimpleNamespace
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'original.pdf';p.write_bytes(b'bound-pdf');report=self.report()
   report.update(pdfPath=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),parser='pypdf')
   fake=SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda:'真正的PDF文字，并非保存的引句')])
   with patch('pypdf.PdfReader',return_value=fake):
    with self.assertRaisesRegex(ValueError,'重新解析结果不一致'):verify_pdf_pages(report)
 def test_missing_parser_requires_reprepare(self):
  from research_report_reading import verify_pdf_pages
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'original.pdf';p.write_bytes(b'bound-pdf');report=self.report()
   report.update(pdfPath=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
   with self.assertRaisesRegex(ValueError,'解析器记录'):verify_pdf_pages(report)
 @patch('research_report_reading.verify_pdf_pages',return_value='pdf-reparsed-pages-matched')
 def test_chain_missing_sections_stay_missing_and_false_quote_rejected(self,mock_verify):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);pdf=p/'original.pdf';pdf.write_bytes(b'original');r=self.report();r.update(pdfPath=str(pdf),sha256=hashlib.sha256(pdf.read_bytes()).hexdigest())
   archive=p/'archive.json';archive.write_text(json.dumps(dict(asOf='2026-10-05',reports=[r])),encoding='utf8')
   e=dict(text='上游材料披露，不推断具名供应商',evidence=[dict(page=1,quote='这是原文披露的完整证据')])
   analysis=dict(reportId='a',logic=[e],assumptions=[e],depth=[e],industryChain=dict(upstream=[e],gaps=['客户名单缺失']))
   analysis['policyAnalysis']=dict(scope=[e])
   spec=dict(archive=str(archive),analyses=[analysis]);result=build(spec,p/'out')
   self.assertEqual(result['analyses'][0]['industryChain']['downstream'],[]);self.assertEqual(result['analyses'][0]['policyAnalysis']['transmission'],[])
   md=(p/'out/研报精读.md').read_text(encoding='utf8');self.assertIn('本次资料未支持此环节',md);self.assertIn('客户名单缺失',md)
   analysis['industryChain']['upstream']=[dict(text='伪造关系',evidence=[dict(page=1,quote='不存在的供应商关系证据')])]
   with self.assertRaises(ValueError):build(spec,p/'rejected')
   self.assertFalse((p/'rejected').exists())
 def test_origin_assessment_duplicate_and_unknown(self):
  from research_report_reading import origin_assessment
  reports={'a':dict(sha256='same',originGroup='one'),'b':dict(sha256='same',originGroup='two')}
  result=origin_assessment(['a','b'],reports)
  self.assertEqual(result['distinctFileCount'],1);self.assertIn('相同PDF',result['note'])
  reports['b']=dict(sha256='other',originGroup=' ')
  result=origin_assessment(['a','b'],reports)
  self.assertEqual(result['unknownOriginCount'],1);self.assertIn('未确认',result['note'])
 @patch('research_report_reading.verify_pdf_pages',return_value='pdf-reparsed-pages-matched')
 def test_unread_report_has_human_reason(self,m):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);pdf=p/'original.pdf';pdf.write_bytes(b'original');r=self.report();r.update(pdfPath=str(pdf),sha256=hashlib.sha256(pdf.read_bytes()).hexdigest())
   missing=dict(id='b',title='扫描报告',status='manual-review',pdfPath=str(pdf),sha256=hashlib.sha256(pdf.read_bytes()).hexdigest())
   archive=p/'archive.json';archive.write_text(json.dumps(dict(asOf='2026-10-05',reports=[r,missing])),encoding='utf8')
   e=dict(text='解释',evidence=[dict(page=1,quote='这是原文披露的完整证据')])
   result=build(dict(archive=str(archive),analyses=[dict(reportId='a',logic=[e],assumptions=[e],depth=[e])]),p/'out')
   self.assertEqual(result['unreadReports'],['b']);self.assertIn('正文提取不足',(p/'out/研报精读.md').read_text(encoding='utf8'));self.assertEqual(len(result['sourceFiles']),2);self.assertFalse(result['sourceFiles'][1]['analysed']);self.assertIn('sources/report-2.pdf',(p/'out/研报精读.md').read_text(encoding='utf8'))
 @patch('research_report_reading.verify_pdf_pages',return_value='pdf-reparsed-pages-matched')
 def test_unread_changed_pdf_rejected_before_delivery(self,m):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);pdf=p/'original.pdf';pdf.write_bytes(b'original');r=self.report();r.update(pdfPath=str(pdf),sha256=hashlib.sha256(pdf.read_bytes()).hexdigest())
   missing=dict(id='b',title='扫描报告',status='manual-review',pdfPath=str(pdf),sha256='changed')
   archive=p/'archive.json';archive.write_text(json.dumps(dict(asOf='2026-10-05',reports=[r,missing])),encoding='utf8')
   e=dict(text='解释',evidence=[dict(page=1,quote='这是原文披露的完整证据')])
   with self.assertRaisesRegex(ValueError,'原PDF变化'):build(dict(archive=str(archive),analyses=[dict(reportId='a',logic=[e],assumptions=[e],depth=[e])]),p/'out')
   self.assertFalse((p/'out').exists())
 @patch('research_report_reading.verify_pdf_pages',return_value='pdf-reparsed-pages-matched')
 def test_policy_invalid_structure_and_quote_rejected(self,m):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);pdf=p/'original.pdf';pdf.write_bytes(b'original');r=self.report();r.update(pdfPath=str(pdf),sha256=hashlib.sha256(pdf.read_bytes()).hexdigest())
   archive=p/'archive.json';archive.write_text(json.dumps(dict(asOf='2026-10-05',reports=[r])),encoding='utf8')
   e=dict(text='解释',evidence=[dict(page=1,quote='这是原文披露的完整证据')])
   for n,policy in enumerate([{},dict(unknown=[e]),dict(scope='错误类型'),dict(timing=[dict(text='生效日',evidence=[dict(page=1,quote='不存在的政策生效日期')])])]):
    analysis=dict(reportId='a',logic=[e],assumptions=[e],depth=[e],policyAnalysis=policy)
    with self.assertRaises(ValueError):build(dict(archive=str(archive),analyses=[analysis]),p/str(n))
    self.assertFalse((p/str(n)).exists())
 def test_citation_scope_counts_unique_pages_not_accuracy(self):
  from research_report_reading import citation_scope
  a=dict(layers=dict(logic=[dict(evidence=[dict(page=2),dict(page=2)])]),policyAnalysis=dict(scope=[dict(evidence=[dict(page=4)])]))
  r=citation_scope(a,dict(pages=[{}, {}, {}, {}, {}]));self.assertEqual(r['citedPages'],[2,4]);self.assertEqual(r['documentPageCount'],5);self.assertEqual(r['status'],'located-excerpts-not-full-document-verification')
 def test_underlying_sources_shared_and_unknown(self):
  from research_report_reading import underlying_source_assessment
  r=underlying_source_assessment(['a','b'],{'a':['AVC-2026H1-retail'],'b':['AVC-2026H1-retail']})
  self.assertEqual(r['distinctDeclaredSourceCount'],1);self.assertEqual(r['sharedDeclaredSources'],['AVC-2026H1-retail']);self.assertFalse(r['independentEvidenceConfirmed'])
  self.assertEqual(underlying_source_assessment(['a','b'],{'a':['one'],'b':[]})['unknownSourceReportCount'],1)
  for invalid in [{'a':['one']},{'a':['one'],'b':['two'],'c':['extra']},{'a':['one',' one '],'b':[]},{'a':'one','b':[]}]:
   with self.assertRaises(ValueError):underlying_source_assessment(['a','b'],invalid)
 def test_comparison_pages_included_in_report_citation_scope(self):
  from research_report_reading import include_comparison_citations
  a=dict(reportId='a',citationScope=dict(citedPages=[1],citedPageCount=1,documentPageCount=5,status='located-excerpts-not-full-document-verification'))
  comparisons=[dict(evidence=[dict(reportId='a',evidence=[dict(page=3),dict(page=3)]),dict(reportId='b',evidence=[dict(page=4)])])]
  include_comparison_citations(a,comparisons)
  self.assertEqual(a['citationScope']['citedPages'],[1,3]);self.assertEqual(a['citationScope']['comparisonCitedPages'],[3]);self.assertEqual(a['citationScope']['citedPageCount'],2)
class ComparisonBasisTests(unittest.TestCase):
 def test_missing_basis_is_not_confirmed(self):
  from research_report_reading import comparison_basis
  self.assertEqual(comparison_basis(['a','b'],None)['status'],'unconfirmed')
 def test_different_periods_not_same_question_conflict(self):
  from research_report_reading import comparison_basis
  a=dict(subject='现金流',period='2026H1',definition='累计经营现金流')
  b=dict(a,period='2026Q2')
  self.assertEqual(comparison_basis(['a','b'],dict(a=a,b=b))['differences'],['period'])
  self.assertEqual(comparison_basis(['a','b'],dict(a=a,b=a))['status'],'declared-aligned-not-verified')
 def test_invalid_or_partial_basis_rejected(self):
  from research_report_reading import comparison_basis
  for mapping in [{},{'a':{}},{'a':{},'b':{}},{'a':dict(subject='x',period=' ',definition='x'),'b':dict(subject='x',period='x',definition='x')}]:
   with self.assertRaises(ValueError):comparison_basis(['a','b'],mapping)
class ComparisonDisplayTests(unittest.TestCase):
 def test_unconfirmed_and_mismatched_basis_do_not_display_consensus(self):
  from research_report_reading import comparison_display_kind
  for kind in ['agreement','difference']:
   self.assertEqual(comparison_display_kind(kind,dict(status='unconfirmed')),'viewpoint-comparison')
   self.assertEqual(comparison_display_kind(kind,dict(status='declared-different')),'not-comparable')
   self.assertEqual(comparison_display_kind(kind,dict(status='declared-aligned-not-verified')),kind)
  self.assertEqual(comparison_display_kind('not-comparable',dict(status='unconfirmed')),'not-comparable')
if __name__=='__main__':unittest.main()
