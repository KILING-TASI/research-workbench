import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from research_evidence import cross_validate
from cross_period_review import review,export
class SourceIndependence(unittest.TestCase):
 def test_knowledge_conflicting_duplicate_verification_not_selected(self):
  from research_evidence import knowledge_add
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);pdf=root/'source.pdf';pdf.write_bytes(b'%PDF-selected-test-only');verification=root/'verification.json'
   verification.write_text(json.dumps(dict(type='original-document-verification',status='passed',sha256=hashlib.sha256(pdf.read_bytes()).hexdigest(),sourceUrl='https://example.org/report',reportDate='2026-06-30',publishedAt='2026-08-29',fields=[dict(id='x',label='收入',status='matched',actual=200),dict(id='x',label='收入',status='matched',actual=100)])),encoding='utf-8')
   with self.assertRaisesRegex(ValueError,'核验字段ID重复'):knowledge_add(dict(code='600036',kind='stock',period='2026-06-30',publishedAt='2026-08-29',sourcePath=str(pdf),sourceUrl='https://example.org/report',verificationPath=str(verification),facts=[dict(id='x',field='revenue',originalLabel='收入',value=100,unit='元',currency='CNY',basis='H1',statementScope='consolidated')]),root/'store')
   self.assertEqual(list((root/'store/research-data/knowledge/stock/600036/versions').glob('*.json')),[])
 def test_source_dates_cannot_reverse_disclosure_order(self):
  for change in [{'period':'2026-09-30'},{'retrievedAt':'2026-08-28'}]:
   row=self.row('a','issuer','hash-a');row.update(change)
   with self.assertRaises(ValueError):cross_validate(dict(asOf='2026-10-05',observations=[row]))
 def row(self,source,publisher,digest):
  return dict(entityId='stock:600036',field='revenue',period='2026-06-30',periodBasis='H1',statementScope='consolidated',basis='reported',unit='CNY',currency='CNY',sourceId=source,publisher=publisher,sourceHash=digest,publishedAt='2026-08-29',value=100)
 def test_compact_dates_do_not_pass_cutoff_comparison(self):
  for field in ['period','publishedAt']:
   row=self.row('a','issuer','hash-a');row[field]=row[field].replace('-','')
   with self.assertRaises(ValueError):cross_validate(dict(asOf='2026-10-05',observations=[row]))
 def test_field_match_does_not_certify_official_publisher(self):
  from research_evidence import knowledge_add
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);pdf=root/'source.pdf';pdf.write_bytes(b'%PDF-selected-test-only')
   signature=hashlib.sha256(pdf.read_bytes()).hexdigest();verification=root/'verification.json'
   verification.write_text(json.dumps(dict(type='original-document-verification',status='passed',sha256=signature,sourceUrl='https://example.org/report',reportDate='2026-06-30',publishedAt='2026-08-29',fields=[dict(id='x',label='收入',status='matched',actual=100)])),encoding='utf-8')
   r=knowledge_add(dict(code='600036',kind='stock',period='2026-06-30',publishedAt='2026-08-29',sourcePath=str(pdf),sourceUrl='https://example.org/report',verificationPath=str(verification),facts=[dict(id='x',field='revenue',originalLabel='收入',value=100,unit='元',currency='CNY',basis='H1',statementScope='consolidated')]),root/'store')
   self.assertEqual(r['evidenceLevel'],'original-fields-matched-authority-unverified')
 def test_retrieval_clock_rejects_invalid_and_marks_retrospective(self):
  for value in ['20261005','00000000','2026-10-05invalid',True]:
   row=self.row('a','issuer','hash-a');row['retrievedAt']=value
   with self.assertRaises(ValueError):cross_validate(dict(asOf='2026-10-05',observations=[row]))
  row=self.row('a','issuer','hash-a');row['retrievedAt']='2026-10-06T01:00:00+00:00'
  r=cross_validate(dict(asOf='2026-10-05',observations=[row]))
  self.assertEqual(r['groups'][0]['sources'][0]['pointInTime'],'retrospective-copy')
 def test_same_publisher_different_files_is_one_source(self):
  r=cross_validate(dict(asOf='2026-10-05',observations=[self.row('a','issuer','hash-a'),self.row('b','issuer','hash-b')]))['groups'][0]
  self.assertEqual(r['distinctSourceCount'],1);self.assertEqual(r['status'],'insufficient-independent-sources')
 def test_republished_same_file_and_publisher_chain_is_one(self):
  r=cross_validate(dict(asOf='2026-10-05',observations=[self.row('a','issuer','hash-a'),self.row('b','mirror','hash-a'),self.row('c','mirror','hash-b')]))['groups'][0]
  self.assertEqual(r['distinctSourceCount'],1)
 def test_same_source_difference_still_visible(self):
  a=self.row('a','issuer','hash-a');b=self.row('b','issuer','hash-b');b['value']=200
  r=cross_validate(dict(asOf='2026-10-05',observations=[a,b]))['groups'][0]
  self.assertEqual(r['numericAgreement'],'divergence');self.assertEqual(r['maxAbsoluteDifference'],'100')
 def test_distinct_declared_publishers_and_hashes(self):
  r=cross_validate(dict(asOf='2026-10-05',observations=[self.row('a','issuer','hash-a'),self.row('b','vendor','hash-b')]))['groups'][0]
  self.assertEqual(r['distinctSourceCount'],2)
class CrossPeriod(unittest.TestCase):
 def setUp(self):
  from pypdf import PdfWriter
  self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name);p=self.base/'original.pdf'
  w=PdfWriter();w.add_blank_page(width=300,height=300);w.add_blank_page(width=300,height=300)
  with p.open('wb') as f:w.write(f)
  source=dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),page=1)
  a=dict(entityId='stock:600036',field='revenue',period='2025-06-30',publishedAt='2026-08-29',periodBasis='H1',statementScope='consolidated',basis='reported',unit='CNY',currency='CNY',value=100,source=source,methods=dict(definitionVersion='revenue-v1'))
  b=copy.deepcopy(a);b.update(period='2026-06-30',value=110);b['source']['page']=2
  self.spec=dict(asOf='2026-10-05',requiredMethodKeys=['definitionVersion'],pairs=[dict(before=a,after=b)])
 def tearDown(self):self.temp.cleanup()
 def test_comparable_and_source_integrity_do_not_certify_fields(self):
  r=review(self.spec)['rows'][0];self.assertEqual(r['delta'],'10');self.assertEqual(r['changePct'],'10.0');self.assertEqual(r['evidence'][0]['fieldVerification'],'not-verified')
 def test_method_difference_blocks_values(self):
  self.spec['pairs'][0]['after']['methods']['definitionVersion']='revenue-v2'
  r=review(self.spec)['rows'][0];self.assertIsNone(r['delta']);self.assertIsNone(r['changePct'])
 def test_missing_method_blocks(self):
  self.spec['pairs'][0]['before']['methods']={}
  self.assertEqual(review(self.spec)['rows'][0]['status'],'blocked-method-missing')
 def test_explicit_restatement_warning_blocks(self):
  self.spec['pairs'][0]['after']['comparabilityWarning']='比较期已经重述，未核对调整桥接'
  self.assertIsNone(review(self.spec)['rows'][0]['delta'])
 def test_zero_or_negative_baseline_no_percentage(self):
  for v in [0,-100]:
   self.spec['pairs'][0]['before']['value']=v
   self.assertIsNone(review(self.spec)['rows'][0]['changePct'])
 def test_same_period_is_revision(self):
  self.spec['pairs'][0]['before']['period']='2026-06-30'
  self.assertEqual(review(self.spec)['rows'][0]['status'],'same-period-revision')
 def test_changed_pdf_rejected(self):
  (self.base/'original.pdf').write_bytes(b'%PDF-changed')
  with self.assertRaisesRegex(ValueError,'哈希'):review(self.spec)
 def test_future_disclosure_rejected(self):
  self.spec['pairs'][0]['after']['publishedAt']='2026-10-06'
  with self.assertRaises(ValueError):review(self.spec)
 def test_export_preserves_distinct_page_links_and_missing_result(self):
  self.spec['pairs'][0]['after']['methods']['definitionVersion']='v2'
  out=self.base/'export';export(self.spec,out)
  text=(out/'跨期研究.html').read_text('utf-8')
  self.assertIn('#page=1',text);self.assertIn('#page=2',text);self.assertIn('不计算跨期变化',text)
  self.assertEqual(len(list((out/'sources').glob('*.pdf'))),1)
 def test_relocatable_replay_and_report_mutation_blocked(self):
  import shutil
  from cross_period_review import replay
  out=self.base/'export';export(self.spec,out);moved=self.base/'moved';shutil.copytree(out,moved)
  self.assertEqual(replay(moved)['status'],'replayed-identical-declared-results')
  (moved/'跨期研究.md').write_text('changed')
  with self.assertRaisesRegex(ValueError,'快照文件'):replay(moved)

class CrossPeriodInputTests(unittest.TestCase):
 setUp=CrossPeriod.setUp
 tearDown=CrossPeriod.tearDown
 def test_boolean_method_not_consistent_declaration(self):
  for side in ['before','after']:self.spec['pairs'][0][side]['methods']['definitionVersion']=True
  with self.assertRaisesRegex(ValueError,'口径须'):review(self.spec)
 def test_compact_date_and_unknown_method_rejected(self):
  self.spec['asOf']='20261005'
  with self.assertRaises(ValueError):review(self.spec)
  self.spec['asOf']='2026-10-05';self.spec['pairs'][0]['before']['methods']['madeUp']='v1'
  with self.assertRaisesRegex(ValueError,'未知'):review(self.spec)
 def test_row_warning_requires_text(self):
  self.spec['pairs'][0]['after']['comparabilityWarning']={'note':'changed'}
  with self.assertRaisesRegex(ValueError,'警告须'):review(self.spec)
 def test_duplicate_json_rejected(self):
  from cross_period_review import load_json
  with self.assertRaises(ValueError):load_json('{"value":1,"value":2}')
  for value in ['1e999','-1e999','NaN']:
   with self.assertRaises(ValueError):load_json('{"value":'+value+'}')
