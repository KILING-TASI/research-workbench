import copy,unittest,tempfile,hashlib
from pathlib import Path
from unittest.mock import patch,MagicMock
from fund_depth import changes,attribution,manager
class Tests(unittest.TestCase):
 def test_classification_unknown_and_conflict(self):
  a={'code':'000001','reportDate':'2025-12-31','publishedAt':'2026-03-31','sourceUrl':'https://example.org/a','weightBasis':'equity','taxonomy':'style','taxonomyVersion':'1','taxonomyVerified':True,'categories':[{'name':'价值','weight':.8},{'name':'成长','weight':.2}]};b=copy.deepcopy(a);b.update(reportDate='2026-06-30',publishedAt='2026-08-31',categories=[{'name':'价值','weight':.3},{'name':'成长','weight':.7}]);s={'code':'000001','asOf':'2026-10-03','reports':[a,b]};self.assertAlmostEqual(changes(s)['pairs'][0]['totalVariationPct'],50);b['taxonomyVerified']=False;self.assertIsNone(changes(s)['pairs'][0]['totalVariationPct']);self.assertIsNone(changes(s)['pairs'][0]['rows'][0]['changePp']);b['code']='000002'
  with self.assertRaises(ValueError):changes(s)
 def test_missing_return_is_not_zero(self):
  s={'code':'000001','base':{'asOf':'2026-10-03'},'weights':[{'industry':'科技'}],'returns':[]};self.assertEqual(attribution(s)['type'],'industry-attribution-gap')
 def test_unmatched_or_duplicate_industry_return_not_silently_ignored(self):
  s={'code':'000001','base':{'asOf':'2026-10-03'},'weights':[{'industry':'科技'}],'returns':[{'industry':'医药'}]}
  with self.assertRaisesRegex(ValueError,'未匹配'):attribution(s)
  s['returns']=[{'industry':'科技'},{'industry':'科技'}]
  with self.assertRaisesRegex(ValueError,'重复'):attribution(s)
 def test_manager_rejects_nonannual_report(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'pdf';p.write_bytes(b'pdf')
   s={'pdf':str(p),'sha256':hashlib.sha256(b'pdf').hexdigest(),'identityText':'某基金2026年中期报告','code':'000001','reportDate':'2026-06-30','publishedAt':'2026-08-31','asOf':'2026-10-03','sourceUrl':'https://example.org/report.pdf'}
   with self.assertRaisesRegex(ValueError,'仅解析年报'):manager(s)
 def test_identity_text_required(self):
  with self.assertRaisesRegex(ValueError,'身份文本'):manager({'identityText':' '})
 def test_header_excluded_and_empty_heading_not_success(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'pdf';p.write_bytes(b'pdf');s={'pdf':str(p),'sha256':hashlib.sha256(b'pdf').hexdigest(),'identityText':'某基金2025年年度报告','code':'000001','reportDate':'2025-12-31','publishedAt':'2026-03-31','asOf':'2026-10-03','sourceUrl':'https://example.org/report.pdf'}
   doc=MagicMock();doc.__enter__.return_value=doc;page=MagicMock();doc.pages=[page]
   page.extract_text.return_value=s['identityText']+'\n4.4 管理人对报告期内投资策略的说明\n'+s['identityText']
   with patch('pdfplumber.open',return_value=doc):
    r=manager(s);self.assertEqual(r['status'],'not-found');self.assertEqual(r['sections'],[]);self.assertEqual(len(r['excludedLines']),2)
   page.extract_text.return_value+='\n实际观点正文'
   with patch('pdfplumber.open',return_value=doc):
    r=manager(s);self.assertEqual(r['sections'][0]['passages'][0]['text'],'实际观点正文')
 def test_attribution_version_missing_or_conflicting(self):
  s={'code':'000001','base':{'asOf':'2026-10-03','industryVersion':'SW2021'},'weights':[{'industry':'科技','industryVersion':'SW2021'}],'returns':[{'industry':'科技'}]}
  self.assertIn('missingInputs',attribution(s))
  s['returns'][0]['industryVersion']='SW2014'
  with self.assertRaisesRegex(ValueError,'版本冲突'):attribution(s)
 def test_matched_version_preserved_in_result(self):
  base={'start':'2026-01-01','end':'2026-06-30','asOf':'2026-10-03','weightDate':'2025-12-31','industrySystem':'SW','industryVersion':'SW2021','basis':'disclosed-snapshot-estimate','returnBasis':'total-return'}
  s={'code':'000001','base':base,'weights':[{'industry':'科技','industryVersion':'SW2021','portfolioWeight':1,'benchmarkWeight':1,'sourceUrl':'https://example.org/weight'}],'returns':[{'industry':'科技','industryVersion':'SW2021','industrySystem':'SW','start':base['start'],'end':base['end'],'portfolioReturnPct':8,'benchmarkReturnPct':5,'sourceUrl':'https://example.org/return'}]}
  r=attribution(s);self.assertEqual(r['industryVersion'],'SW2021');self.assertEqual(r['activeSnapshotReturnPp'],3)
if __name__=='__main__':unittest.main()
