import unittest,tempfile,json
from pathlib import Path
from icbc_report_catalog import select,run
class Tests(unittest.TestCase):
 def data(self):return dict(code='0000',data=dict(total=100,hasNextPage=True,content=[dict(fundCode=['000991','011473'],announcementName='2025年度报告',announcementDate='2026-03-31',updatedTime='2026-03-30 10:00:00',fileUrl='/20260330/report.pdf')]))
 def test_identity_title_and_separate_dates(self):
  d=self.data();r=select(d,'000991','2025年度报告');self.assertEqual(len(r),1);self.assertFalse(r[0]['firstPublicTimeVerified']);self.assertNotEqual(r[0]['publishedDate'],r[0]['publisherUpdatedTime'][:10]);self.assertEqual(select(d,'000991','2026中期报告'),[])
  with self.assertRaises(ValueError):select(d,'006228','2025年度报告')
 def test_external_or_traversal_path_rejected(self):
  for url in ['https://other.test/a.pdf','/20260330/../a.pdf']:
   d=self.data();d['data']['content'][0]['fileUrl']=url
   with self.assertRaises(ValueError):select(d,'000991','2025年度报告')
 def test_failure_preserved_and_partial_not_promoted(self):
  with tempfile.TemporaryDirectory() as d:
   r=run('000991','2025年度报告',Path(d)/'ok',lambda u:json.dumps(self.data()).encode());self.assertFalse(r['completeCatalogVerified']);self.assertEqual(r['returnedCount'],1)
   def fail(u):raise TimeoutError('network timeout')
   r=run('000991','2025年度报告',Path(d)/'bad',fail);self.assertEqual(r['status'],'failed');self.assertIn('TimeoutError',r['error'])
