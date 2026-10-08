import unittest,tempfile
from pathlib import Path
from unittest.mock import patch
from efunds_document_binding import select,run,report_identity
class Tests(unittest.TestCase):
 def test_matching_report_identity_before_period_end_is_pending(self):
  title='目标基金2026年中期报告';payload=self.sample();payload['data']['data'][0]['title']=title
  with tempfile.TemporaryDirectory() as t,patch('efunds_document_binding.read_pages',return_value=[(1,title+' 基金主代码159915 2026年6月30日')]):
   r=run('159915',title,'2026-01-31','2026-10-03',Path(t)/'out',fetch=lambda _:payload,download_fn=lambda _:b'%PDFtest')
  self.assertEqual(r['periodicReportIdentity']['status'],'pending');self.assertEqual(r['periodicReportIdentity']['publicationTimingStatus'],'before-report-period-end');self.assertIsNone(r['fees'])
 def test_catalog_shape_and_credential_url_rejected(self):
  for payload in [None,[],dict(status=True,data=dict(data=[])),dict(status=1,data=dict(data=[None]))]:
   with self.assertRaises(ValueError):select(payload,'招募书','2026-01-31')
  p=self.sample();p['data']['data'][0]['path']='https://user:password@cdn.efunds.com.cn/a.pdf'
  with self.assertRaises(ValueError):select(p,'招募书','2026-01-31')
 def test_archived_path_and_page_scope(self):
  with tempfile.TemporaryDirectory() as t,patch('efunds_document_binding.read_pages',return_value=[(1,'招募书')]):
   r=run('005827','招募书','2026-01-31','2026-10-03',Path(t)/'out',fetch=lambda _:self.sample(),download_fn=lambda _:b'%PDFtest')
   self.assertTrue(Path(r['documentPath']).is_file());self.assertEqual(r['pageCount'],1);self.assertEqual(r['titleCheckedPages'],1);self.assertFalse(r['effectiveVersionVerified'])
 def sample(self):return dict(status=1,data=dict(data=[dict(title='招募书',publishDate='2026-01-31 00:00:00',path='https://cdn.efunds.com.cn/a.pdf')]))
 def test_unique(self):self.assertEqual(select(self.sample(),'招募书','2026-01-31')['title'],'招募书')
 def test_wrong_date(self):
  with self.assertRaises(ValueError):select(self.sample(),'招募书','2025-01-31')
 def test_duplicate(self):
  p=self.sample();p['data']['data']*=2
  with self.assertRaises(ValueError):select(p,'招募书','2026-01-31')
 def test_nonofficial(self):
  p=self.sample();p['data']['data'][0]['path']='https://example.org/a.pdf'
  with self.assertRaises(ValueError):select(p,'招募书','2026-01-31')
 def test_all_public_query_scope(self):
  captured=[]
  with tempfile.TemporaryDirectory() as t,patch('efunds_document_binding.read_pages',return_value=[(1,'招募书')]):
   def fetch(params):captured.append(params);return self.sample()
   r=run('005827','招募书','2026-01-31','2026-10-03',Path(t)/'out',fetch=fetch,download_fn=lambda _:b'%PDFtest',catalog_scope='all-public')
   self.assertNotIn('catalogAlias',captured[0]);self.assertEqual(r['catalogScope'],'all-public')
 def test_legal_scope_retained(self):
  captured=[]
  with tempfile.TemporaryDirectory() as t,patch('efunds_document_binding.read_pages',return_value=[(1,'招募书')]):
   def fetch(params):captured.append(params);return self.sample()
   run('005827','招募书','2026-01-31','2026-10-03',Path(t)/'out',fetch=fetch,download_fn=lambda _:b'%PDFtest')
   self.assertEqual(captured[0]['catalogAlias'],'xxplflwj')
 def test_invalid_scope_rejected_before_query(self):
  with tempfile.TemporaryDirectory() as t:
   def fetch(_):raise AssertionError('不能发起请求')
   with self.assertRaises(ValueError):run('005827','招募书','2026-01-31','2026-10-03',Path(t)/'out',fetch=fetch,catalog_scope='unknown')
 def test_period_identity(self):
  r=report_identity([(5,'基金主代码159915 报告期末2026年6月30日')],'159915','目标基金2026年中期报告');self.assertEqual(r['status'],'matched')
 def test_wrong_code_or_period_pending(self):
  for text in ['基金主代码159916 报告期末2026年6月30日','基金主代码159915 报告期末2025年6月30日']:
   self.assertEqual(report_identity([(5,text)],'159915','目标基金2026年中期报告')['status'],'pending')
 def test_legal_not_forced_report_date(self):
  self.assertEqual(report_identity([(1,'更新招募书')],'159915','更新招募说明书')['status'],'not-periodic-report')
 def test_pending_report_does_not_deliver_fees(self):
  payload=self.sample();payload['data']['data'][0]['title']='目标基金2026年中期报告'
  with tempfile.TemporaryDirectory() as t,patch('efunds_document_binding.read_pages',return_value=[(1,'目标基金2026年中期报告 基金主代码159916 2026年6月30日')]):
   r=run('159915','目标基金2026年中期报告','2026-01-31','2026-10-03',Path(t)/'out',fetch=lambda _:payload,download_fn=lambda _:b'%PDFtest',catalog_scope='all-public')
   self.assertTrue(r['titleMatched']);self.assertEqual(r['periodicReportIdentity']['status'],'pending');self.assertIsNone(r['fees'])
 def test_chinese_year_and_halfyear(self):
  r=report_identity([(5,'基金主代码159915 2026年6月30日')],'159915','目标基金二〇二六年半年度报告');self.assertEqual(r['status'],'matched')
 def test_quarter_end(self):
  r=report_identity([(5,'基金主代码159915 2026年3月31日')],'159915','目标基金2026年第1季度报告');self.assertEqual(r['status'],'matched');self.assertEqual(r['expectedPeriodEnd'],'2026-03-31')
 def test_unsupported_period_not_legal(self):
  for title in ['目标基金2026年第5季度报告','目标基金本年中期报告']:
   self.assertEqual(report_identity([(5,'基金主代码159915 2026年6月30日')],'159915',title)['status'],'pending')
if __name__=='__main__':unittest.main()
