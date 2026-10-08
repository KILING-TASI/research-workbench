import unittest,tempfile,json,hashlib
from pathlib import Path
from unittest.mock import patch,Mock
from company_report_batch import run
class ResumeTests(unittest.TestCase):
 def prepare(self,root):
  old=root/'old';(old/'600887').mkdir(parents=True);raw=b'%PDF-test';(old/'600887'/'report.pdf').write_bytes(raw)
  parsed=dict(parser='test',pages=[dict(page=1,text='fixture')])
  good=dict(code='600887',period='2026-06-30',asOf='2026-10-05',parseStatus='parsed',downloadStatus='downloaded',disclosureStatus='explicit-source-unverified',numericVerification='not-attempted',error=None,candidates=[],fileSha256=hashlib.sha256(raw).hexdigest(),**parsed)
  failed=dict(code='600309',parseStatus='failed',downloadStatus='failed')
  data=dict(period='2026-06-30',asOf='2026-10-05',companies=[good,failed]);(old/'result.json').write_text(json.dumps(data),encoding='utf8')
  return dict(period=data['period'],asOf=data['asOf'],companies=[dict(code=r['code']) for r in data['companies']],resumeFrom=str(old/'result.json')),parsed
 def test_verified_success_reused_failure_retried(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);spec,parsed=self.prepare(root);fetch=Mock(return_value=b'{"announcements":[],"hasMore":false}')
   with patch('company_report_batch.parse_pdf',return_value=parsed):r=run(spec,root/'new',fetch)
   self.assertEqual(fetch.call_count,1);self.assertIn('remote-revisions-not-checked',r['companies'][0]['reuseStatus']);self.assertEqual(r['companies'][1]['reuseStatus'],'not-reused; acquisition-attempted')
   self.assertTrue((root/'old'/'600887'/'report.pdf').exists())
 def test_corrupt_cache_reacquired(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);spec,parsed=self.prepare(root);(root/'old'/'600887'/'report.pdf').write_bytes(b'changed');fetch=Mock(return_value=b'{"announcements":[],"hasMore":false}')
   r=run(spec,root/'new',fetch);self.assertEqual(fetch.call_count,2);self.assertIn('哈希变化',r['companies'][0]['cacheReviewError'])
 def test_nested_cutoff_tampering_reacquires_instead_of_reuse(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);spec,_=self.prepare(root);path=root/'old'/'result.json';data=json.loads(path.read_text());data['companies'][0]['asOf']='2026-09-01';path.write_text(json.dumps(data))
   fetch=Mock(return_value=b'{"announcements":[],"hasMore":false}')
   with patch('company_report_batch.parse_pdf') as parser:r=run(spec,root/'new',fetch)
   parser.assert_not_called();self.assertEqual(fetch.call_count,2);self.assertIn('截止日不一致',r['companies'][0]['cacheReviewError'])
 def test_changed_scope_rejected_before_output(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);spec,_=self.prepare(root);spec['asOf']='2026-10-06'
   with self.assertRaises(ValueError):run(spec,root/'new')
   self.assertFalse((root/'new').exists())

class AcquisitionDisclosureTests(unittest.TestCase):
 def test_attempt_is_not_success_and_reuse_is_not_remote_refresh(self):
  from company_report_batch import acquisition_summary,acquisition_lines
  rows=[dict(code='600887',reuseStatus='local-pdf-and-pages-reverified; remote-revisions-not-checked'),dict(code='600309',downloadStatus='failed')]
  summary=acquisition_summary(rows)
  self.assertEqual(summary['remoteRevisionCheckPendingCodes'],['600887'])
  self.assertEqual(summary['acquisitionAttemptedCodes'],['600309'])
  text='\n'.join(acquisition_lines(summary));self.assertIn('尝试重新获取',text);self.assertIn('不代表公告版本已更新',text)
