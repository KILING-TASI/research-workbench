import unittest,tempfile,json,subprocess
from pathlib import Path
from unittest.mock import patch
import financial_research_pipeline as f

class Tests(unittest.TestCase):
 def test_matched_counts_without_field_identity_keep_gap(self):
  checks=[dict(status='matched') for _ in f.CHECK_FIELDS]
  result=f.verification_summary(dict(companies=[dict(code='600900',checks=checks,comparativeChecks=checks)]),['600900'])
  self.assertTrue(any('字段身份' in gap for gap in result['companies'][0]['researchGaps']))
  checks=[dict(metric=key,status='matched') for key in f.CHECK_FIELDS]
  result=f.verification_summary(dict(companies=[dict(code='600900',checks=checks,comparativeChecks=checks)]),['600900'])
  self.assertEqual(result['companies'][0]['researchGaps'],[])
  checks.append(dict(checks[0]))
  with self.assertRaisesRegex(ValueError,'重复'):f.verification_summary(dict(companies=[dict(code='600900',checks=checks)]),['600900'])
 def test_bad_pool_or_missing_font_stops_before_collection(self):
  invalid=[None,[],dict(companies=[None]),dict(companies=[dict(code=True)])]
  spec=self.spec();spec['exportFormats']=['pptx'];invalid.append(spec)
  with tempfile.TemporaryDirectory() as folder,patch.object(f,'collect') as collect:
   for index,value in enumerate(invalid):
    out=Path(folder)/str(index)
    with self.subTest(value=value),self.assertRaises(ValueError):f.run(value,out)
    self.assertFalse(out.exists())
   collect.assert_not_called()
 def spec(self):return dict(period='2026-06-30',asOf='2026-10-05',companies=[dict(code='300308',metadata=dict(name='中际旭创',scope='consolidated',currency='CNY',unit='元',classificationVersion='用户分组v1'))])
 def test_invalid_commentary_rejected_before_network_and_output(self):
  for extra in [dict(interpretations={},),dict(interpretations=[],interpretationsPath='missing.json'),dict(comparisonsPath='missing.json')]:
   with self.subTest(extra=extra),tempfile.TemporaryDirectory() as d,patch.object(f,'collect') as collect,patch.object(f,'reports') as reports:
    spec=self.spec();spec.update(extra);out=Path(d)/'run'
    with self.assertRaises((ValueError,FileNotFoundError)):f.run(spec,out)
    collect.assert_not_called();reports.assert_not_called();self.assertFalse(out.exists())
 def test_resume_directory_rejected_before_collection(self):
  with tempfile.TemporaryDirectory() as d,patch.object(f,'collect') as collect:
   spec=self.spec();spec['originalResumeFrom']=d;out=Path(d)/'run'
   with self.assertRaisesRegex(ValueError,'result.json'):f.run(spec,out)
   collect.assert_not_called();self.assertFalse(out.exists())
 def test_quarter_flag_rejects_string_before_collection(self):
  with tempfile.TemporaryDirectory() as d,patch.object(f,'collect') as collect:
   s=self.spec();s['verifyQuarterInputs']='true'
   with self.assertRaises(ValueError):f.run(s,Path(d)/'run')
   collect.assert_not_called()
 def test_quarter_dependency_failure_not_complete(self):
  with tempfile.TemporaryDirectory() as d,patch.object(f,'collect',return_value=dict(status='available')),patch.object(f,'reports',return_value=dict(companies=[],coverage={})),patch.object(f,'financials',side_effect=ValueError('period missing')):
   s=self.spec();s['verifyQuarterInputs']=True;r=f.run(s,Path(d)/'run');self.assertEqual(r['stages']['quarterInputs'],'dependency-missing');self.assertEqual(r['quarterInputReviews'],[])
 def test_invalid_metadata_rejected_before_collect_or_output(self):
  for key,value in [('scope','unknown'),('currency',''),('unit',None),('classificationVersion',' ')]:
   with self.subTest(key=key),tempfile.TemporaryDirectory() as d,patch.object(f,'collect') as collect:
    spec=self.spec();spec['companies'][0]['metadata'][key]=value;p=Path(d)/'run'
    with self.assertRaises(ValueError):f.run(spec,p)
    collect.assert_not_called();self.assertFalse(p.exists())
  with tempfile.TemporaryDirectory() as d,patch.object(f,'collect') as collect:
   spec=self.spec();del spec['companies'][0]['metadata'];p=Path(d)/'run'
   with self.assertRaisesRegex(ValueError,'口径'):f.run(spec,p)
   collect.assert_not_called();self.assertFalse(p.exists())
 def test_original_failure_keeps_financial_and_delivery(self):
  with tempfile.TemporaryDirectory() as d,patch.object(f,'collect',return_value=dict(status='available')),patch.object(f,'reports',side_effect=TimeoutError('timeout')),patch.object(f,'financials') as calc,patch.object(f,'commentary') as note:
   p=Path(d)/'run';r=f.run(self.spec(),p);self.assertEqual(r['stages']['reports'],'failed');self.assertEqual(r['stages']['financials'],'completed');self.assertEqual(r['stages']['commentary'],'not-attempted');self.assertTrue((p/'研究入口.html').exists());calc.assert_called_once();note.assert_not_called()
 def test_financial_failure_keeps_original_and_manifest(self):
  with tempfile.TemporaryDirectory() as d,patch.object(f,'collect',return_value=dict(status='available')),patch.object(f,'reports',return_value=dict(companies=[],coverage={})),patch.object(f,'financials',side_effect=ValueError('period missing')),patch.object(f,'commentary') as note:
   p=Path(d)/'run';r=f.run(self.spec(),p);self.assertEqual(r['stages']['financials'],'failed');self.assertEqual(r['stages']['reports'],'completed');self.assertTrue((p/'result.json').exists());note.assert_not_called()
 def test_missing_original_not_complete(self):
  r=f.verification_summary(None,['300308']);self.assertEqual(r['companies'][0]['matched'],0);self.assertEqual(r['companies'][0]['unverified'],len(f.CHECK_FIELDS))
 def test_metadata_warning_not_cleared_by_numeric_matches(self):
  from financial_source_binding import report_metadata_warnings
  warnings=report_metadata_warnings(dict(disclosureStatus='explicit-source-unverified'))
  self.assertTrue(warnings)
  r=f.verification_summary(dict(companies=[dict(code='000858',checks=[dict(status='matched')]*7,reportMetadataWarnings=warnings)]),['000858'])
  self.assertEqual(r['companies'][0]['reportMetadataWarnings'],warnings);self.assertEqual(r['companies'][0]['matched'],7)
 def test_current_matches_do_not_clear_restatement_warning(self):
  warning=dict(page=7,kind='comparative-restatement-disclosed',warning='比较期间追溯调整，同期资料尚未核验')
  data=dict(companies=[dict(code='600900',checks=[dict(status='matched') for _ in range(7)],comparabilityWarnings=[warning])])
  row=f.verification_summary(data,['600900'])['companies'][0]
  self.assertEqual(row['matched'],7);self.assertEqual(row['comparabilityWarnings'],[warning]);self.assertFalse(row['comparativePeriodVerified'])
 def test_difference_separate_from_matched(self):
  r=f.verification_summary(dict(companies=[dict(code='300308',checks=[dict(status='matched'),dict(status='difference'),dict(status='ambiguous')])]),['300308'])['companies'][0];self.assertEqual((r['matched'],r['differences'],r['unverified']),(1,1,len(f.CHECK_FIELDS)-2))
 def test_malformed_interpretation_file_rejected_before_acquisition(self):
  with tempfile.TemporaryDirectory() as d,patch.object(f,'collect') as collect,patch.object(f,'reports') as reports:
   file=Path(d)/'interpretations.json';file.write_text('{broken',encoding='utf8')
   p=Path(d)/'run';s=self.spec();s['interpretationsPath']=str(file)
   with self.assertRaises(json.JSONDecodeError):f.run(s,p)
   collect.assert_not_called();reports.assert_not_called();self.assertFalse(p.exists())
 def test_comparisons_forwarded(self):
  rows=[dict(codes=['600031','000425'])]
  self.assertEqual(f.commentary_options(dict(comparisons=rows))['comparisons'],rows)
 def test_conflicting_options_rejected(self):
  with self.assertRaisesRegex(ValueError,'同时'):f.commentary_options(dict(comparisons=[],comparisonsPath='some.json'))
 def test_bad_type_rejected(self):
  with self.assertRaisesRegex(ValueError,'列表'):f.commentary_options(dict(comparisons={}))
 def test_comparison_file_supported(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'rows.json';p.write_text('[]',encoding='utf-8-sig')
   self.assertEqual(f.commentary_options(dict(comparisonsPath=str(p))),dict(comparisons=[]))
 def test_comparative_summary_preserves_missing_and_difference(self):
  data=dict(companies=[dict(code='600900',checks=[dict(status='matched')]*7,comparativeChecks=[dict(status='matched')]*5+[dict(status='difference'),dict(status='period-unconfirmed')])])
  row=f.verification_summary(data,['600900'])['companies'][0]
  self.assertEqual((row['comparativeColumnMatched'],row['comparativeColumnDifferences'],row['comparativeColumnUnverified']),(5,1,len(f.CHECK_FIELDS)-6))
  self.assertFalse(row['comparativePeriodVerified'])
class DeliveryAssessmentTests(unittest.TestCase):
 def test_steps_completed_not_input_verification(self):
  stages={k:'completed' for k in ['reports','financials','commentary','excel']}
  summary=f.verification_summary(None,['600309'])
  quarter=f.quarter_verification_summary([],['600309'],False)
  self.assertEqual(f.delivery_assessment(stages,summary,quarter,[])['status'],'partial')
 def test_adjacent_metadata_warning_survives_numeric_matches(self):
  warning={'period':'2025-06-30','warning':'补充文件披露日期未核验'}
  review={'code':'600309','reportMetadataWarnings':[warning],'fields':[{'metric':key,'parts':{part:{'value':1,'status':'supported-inputs-matched','dependencies':[{'status':'matched'}]} for part in ['current','yoy','qoq']}} for key in f.CHECK_FIELDS]}
  quarter=f.quarter_verification_summary([review],['600309'],True)
  self.assertEqual(quarter['companies'][0]['matched'],len(f.CHECK_FIELDS)*3)
  self.assertEqual(quarter['companies'][0]['reportMetadataWarnings'],[warning])
  summary={'companies':[{'code':'600309','matched':7,'supportedFieldCount':7,'comparativeColumnMatched':7,'comparabilityWarnings':[],'reportMetadataWarnings':[]}]}
  result=f.delivery_assessment({k:'completed' for k in ['reports','financials','commentary','excel']},summary,quarter,[])
  self.assertEqual(result['status'],'partial');self.assertTrue(any('相邻报告' in gap for gap in result['gaps']))
 def test_only_supported_scope_can_be_verified(self):
  stages={k:'completed' for k in ['reports','financials','commentary','excel']}
  s=dict(companies=[dict(code='600309',matched=7,supportedFieldCount=7,comparativeColumnMatched=7,comparabilityWarnings=[],reportMetadataWarnings=[])])
  q=dict(companies=[dict(code='600309',requested=True,matched=21,supportedInputGroupCount=21)])
  self.assertEqual(f.delivery_assessment(stages,s,q,[])['status'],'supported-scope-verified')
  self.assertEqual(f.delivery_assessment(stages,s,q,['底稿公式有差异'])['status'],'partial')

class DocumentExportTests(unittest.TestCase):
 def test_font_is_forwarded_to_ppt_export(self):
  with tempfile.TemporaryDirectory() as d,patch.object(f.subprocess,'run',return_value=subprocess.CompletedProcess([],1,'','export fixture')) as process:
   source=Path(d)/'commentary';source.mkdir();(source/'公司与行业点评.md').write_text('# 点评\n正文',encoding='utf-8')
   f.export_documents({'exportFormats':['pptx'],'fontFamily':'Microsoft YaHei'},d,True,'node')
   request=json.loads((Path(d)/'pptx-export-input.json').read_text(encoding='utf-8'))
   self.assertEqual(request['fontFamily'],'Microsoft YaHei');process.assert_called_once()
 def test_invalid_format_rejected(self):
  for value in ['docx',['pdf'],['docx','docx']]:
   with self.assertRaisesRegex(ValueError,'exportFormats'):f.document_formats({'exportFormats':value})
 def test_missing_commentary_does_not_start_export(self):
  with tempfile.TemporaryDirectory() as d:
   result,issues=f.export_documents({'exportFormats':['docx','pptx']},d,False)
   self.assertEqual([r['status'] for r in result.values()],['dependency-missing','dependency-missing']);self.assertEqual(len(issues),2)
 def test_one_format_failure_does_not_discard_other(self):
  def fake_export(request):
   folder=Path(request['outDir']);folder.mkdir(parents=True)
   result={'format':'docx'};(folder/'export-result.json').write_text(json.dumps(result),encoding='utf-8');return result
  with tempfile.TemporaryDirectory() as d,patch('export_financial_docx.export',side_effect=fake_export) as exporter:
   p=Path(d)/'commentary';p.mkdir();(p/'公司与行业点评.md').write_text('# 公司点评\n资料缺口',encoding='utf-8')
   result,issues=f.export_documents({'exportFormats':['docx','pptx']},d,True,None)
   self.assertEqual(result['docx']['status'],'generated-awaiting-review');self.assertEqual(result['pptx']['status'],'dependency-missing');self.assertEqual(len(issues),2);exporter.assert_called_once();self.assertTrue((p/'公司与行业点评.md').is_file())
 def test_successful_generation_still_partial(self):
  stages={k:'completed' for k in ['reports','financials','commentary','excel']}
  result=f.delivery_assessment(stages,{'companies':[]},{'companies':[]},['Word已生成，尚需排版验收'])
  self.assertEqual(result['status'],'partial')

if __name__=='__main__':unittest.main()
