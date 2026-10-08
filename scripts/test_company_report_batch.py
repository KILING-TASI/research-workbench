import unittest,tempfile,json
from pathlib import Path
from company_report_batch import candidates,run
class Tests(unittest.TestCase):
 def test_non_pdf_response_is_not_cached_or_parsed_as_report(self):
  import hashlib
  from unittest.mock import patch
  from company_report_batch import collect_one
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);upload=d/'claimed.pdf';raw=b'<!doctype html><html>temporary response</html>';upload.write_bytes(raw)
   with patch('company_report_batch.parse_pdf') as parser:
    row=collect_one('688180','2026-06-30','2026-10-06',d/'out',uploaded=str(upload))
    parser.assert_not_called()
   self.assertEqual(row['downloadStatus'],'failed');self.assertNotEqual(row['parseStatus'],'parsed')
   self.assertFalse((d/'out/report.pdf').exists())
   self.assertEqual(row['rejectedResponse']['sha256'],hashlib.sha256(raw).hexdigest())
   self.assertEqual(row['rejectedResponse']['bytes'],len(raw))
   self.assertEqual(json.loads((d/'out/result.json').read_text(encoding='utf-8'))['error'],'下载或上传内容不是PDF')
 def test_quarter_title_aliases_do_not_match_operating_data(self):
  import datetime as dt
  for period,title in [('2026-03-31','2026年一季度报告'),('2026-09-30','2026年三季度报告')]:
   published='2026-04-21' if period.endswith('03-31') else '2026-10-21'
   item=dict(secCode='600309',announcementTitle='万华化学'+title,announcementTime=int(dt.datetime.fromisoformat(published).replace(tzinfo=dt.timezone(dt.timedelta(hours=8))).timestamp()*1000),adjunctUrl='finalpage/'+published+'/123.PDF',announcementId='123')
   self.assertEqual(len(candidates([item],'600309',period,'2026-10-31')),1)
   for invalid in [title+'摘要',title.replace('报告','主要经营数据公告'),title.replace('2026','2025')]:
    self.assertEqual(candidates([dict(item,announcementTitle=invalid)],'600309',period,'2026-10-31'),[])
 def test_title_cutoff_identity(self):
  item=dict(secCode='300308',announcementTitle='2026年半年度报告',announcementTime=1787328000000,adjunctUrl='finalpage/2026-08-22/1225491753.PDF',announcementId='x')
  self.assertEqual(len(candidates([item],'300308','2026-06-30','2026-10-05')),1)
  self.assertEqual(candidates([item],'002475','2026-06-30','2026-10-05'),[])
  self.assertEqual(candidates([dict(item,announcementTitle='2026年半年度报告摘要')],'300308','2026-06-30','2026-10-05'),[])
  self.assertEqual(candidates([item],'300308','2026-06-30','2026-08-01'),[])
 def test_notfound_is_not_nonpublication(self):
  with tempfile.TemporaryDirectory() as d:
   result=run(dict(period='2026-06-30',asOf='2026-10-05',companies=[dict(code='300308')]),Path(d)/'out',fetch=lambda *args:json.dumps(dict(announcements=[],hasMore=False)).encode())
   self.assertEqual(result['companies'][0]['disclosureStatus'],'not-found');self.assertEqual(result['companies'][0]['downloadStatus'],'not-attempted')
 def test_catalog_failure(self):
  with tempfile.TemporaryDirectory() as d:
   result=run(dict(period='2026-06-30',asOf='2026-10-05',companies=[dict(code='300308')]),Path(d)/'out',fetch=lambda *args:b'{}')
   self.assertEqual(result['companies'][0]['catalogStatus'],'failed')
 def test_explicit_source_rejects_future_or_mismatched_url_before_fetch(self):
  from unittest.mock import Mock
  doc=dict(code='000858',id='123',title='半年报',publishedAt='2026-10-06',url='https://static.cninfo.com.cn/finalpage/2026-10-06/123.PDF')
  for date,url in [('2026-10-06',doc['url']),('2026-08-29','https://example.com/file.pdf')]:
   with tempfile.TemporaryDirectory() as d:
    fetch=Mock();source=dict(doc,publishedAt=date,url=url)
    r=run(dict(period='2026-06-30',asOf='2026-10-05',companies=[dict(code='000858',sourceDocument=source)]),Path(d)/'out',fetch=fetch)
    fetch.assert_not_called();self.assertEqual(r['companies'][0]['downloadStatus'],'failed');self.assertEqual(r['companies'][0]['catalogStatus'],'not-attempted')


class RequestRetryTests(unittest.TestCase):
 def test_transient_gateway_retries_but_client_error_does_not(self):
  from unittest.mock import patch
  from urllib.error import HTTPError
  from io import BytesIO
  from company_report_batch import request
  with patch('company_report_batch.urlopen',side_effect=[HTTPError('https://example.org',504,'timeout',{},None),BytesIO(b'{}')]) as fetch:
   self.assertEqual(request('https://example.org'),b'{}');self.assertEqual(fetch.call_count,2)
  with patch('company_report_batch.urlopen',side_effect=HTTPError('https://example.org',404,'missing',{},None)) as fetch:
   with self.assertRaises(HTTPError):request('https://example.org')
   self.assertEqual(fetch.call_count,1)

class BankTitleTests(unittest.TestCase):
 def test_half_year_without_nian_excludes_summary(self):
  import datetime as dt
  item=dict(secCode='601398',announcementTitle='工商银行2026半年度报告',announcementTime=int(dt.datetime(2026,8,28,tzinfo=dt.timezone.utc).timestamp()*1000),adjunctUrl='finalpage/2026-08-28/1225527600.PDF',announcementId='1225527600')
  self.assertEqual(len(candidates([item],'601398','2026-06-30','2026-10-05')),1)
  for title in ['工商银行2026半年度报告摘要','工商银行2025半年度报告','工商银行2026半年度主要经营数据']:
   self.assertEqual(candidates([dict(item,announcementTitle=title)],'601398','2026-06-30','2026-10-05'),[])

class PdfIdentityTests(unittest.TestCase):
 def test_code_year_whitespace_is_not_removed_for_code_boundary(self):
  from company_report_batch import parse_pdf
  from unittest.mock import patch,MagicMock
  doc=MagicMock();page=MagicMock();page.extract_text.return_value='证券代码：600276 2026年半年度报告\n'+'经营内容测试 '*30;doc.pages=[page];doc.__enter__.return_value=doc
  with patch('pdfplumber.open',return_value=doc):self.assertEqual(parse_pdf('unused.pdf','600276','2026-06-30')['identityStatus'],'证券代码与报告期标题匹配，数值尚未逐行核验')
 def test_long_number_and_wrong_period_are_rejected(self):
  from company_report_batch import parse_pdf
  from unittest.mock import patch,MagicMock
  for text in ['号码：16002760 2026年半年度报告','证券代码：600276 2025年半年度报告']:
   doc=MagicMock();page=MagicMock();page.extract_text.return_value=text+'经营内容测试 '*30;doc.pages=[page];doc.__enter__.return_value=doc
   with patch('pdfplumber.open',return_value=doc):
    with self.assertRaisesRegex(ValueError,'未确认'):parse_pdf('unused.pdf','600276','2026-06-30')

class VersionChoiceReportTests(unittest.TestCase):
 def test_conflicting_versions_are_visible_and_not_downloaded(self):
  import datetime as dt
  rows=[dict(secCode='600276',announcementTitle=title,announcementTime=int(dt.datetime(2026,8,28,tzinfo=dt.timezone.utc).timestamp()*1000),adjunctUrl='finalpage/2026-08-28/'+id+'.PDF',announcementId=id) for id,title in [('123','2026年半年度报告'),('124','2026年半年度报告（更正后）')]]
  calls=[]
  def fetch(url,*args):
   calls.append(url);return json.dumps(dict(announcements=rows,hasMore=False)).encode()
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'out';result=run(dict(period='2026-06-30',asOf='2026-10-05',companies=[dict(code='600276')]),out,fetch)
   self.assertEqual(result['companies'][0]['downloadStatus'],'conflict');self.assertEqual(len(calls),1)
   report=(out/'财报覆盖.md').read_text(encoding='utf8')
   for text in ['更正后','123','124','未自动认定最新版本优先','查看原文']:self.assertIn(text,report)

class HistoricalWindowTests(unittest.TestCase):
 def test_wide_miss_requeries_historical_window(self):
  from unittest.mock import patch
  from company_report_batch import collect_one
  import datetime as dt
  item=dict(secCode='600406',announcementTitle='2025年第一季度报告',announcementTime=int(dt.datetime(2025,4,29,tzinfo=dt.timezone.utc).timestamp()*1000),adjunctUrl='finalpage/2025-04-29/123.PDF',announcementId='123')
  calls=[]
  def fetch(url,data=None):
   if data is None:return b'%PDF fake'
   calls.append(data['seDate']);return json.dumps(dict(announcements=[item] if data['seDate'].endswith('2026-03-31') else [],hasMore=False)).encode()
  with tempfile.TemporaryDirectory() as d,patch('company_report_batch.parse_pdf',return_value=dict(pages=[],identityStatus='test')):
   r=collect_one('600406','2025-03-31','2026-10-06',Path(d)/'out',fetch=fetch)
   self.assertEqual(r['downloadStatus'],'downloaded');self.assertEqual(calls,['2025-03-31~2026-10-06','2025-03-31~2026-03-31'])
 def test_recheck_does_not_silently_select_conflicting_versions(self):
  from unittest.mock import patch
  from company_report_batch import collect_one
  import datetime as dt
  item=dict(secCode='600406',announcementTitle='2025年第一季度报告',announcementTime=int(dt.datetime(2025,4,29,tzinfo=dt.timezone.utc).timestamp()*1000),adjunctUrl='finalpage/2025-04-29/123.PDF',announcementId='123')
  def fetch(url,data=None):return json.dumps(dict(announcements=[item,dict(item,announcementId='124',adjunctUrl='finalpage/2025-04-29/124.PDF')] if data['seDate'].endswith('2026-03-31') else [],hasMore=False)).encode()
  with tempfile.TemporaryDirectory() as d:
   r=collect_one('600406','2025-03-31','2026-10-06',Path(d)/'out',fetch=fetch);self.assertEqual(r['downloadStatus'],'conflict')

class CandidateIntegrityTests(unittest.TestCase):
 def test_repeat_catalog_item_not_false_version_conflict(self):
  item=dict(secCode='300308',announcementTitle='2026年半年度报告',announcementTime=1787328000000,adjunctUrl='finalpage/2026-08-22/123.PDF',announcementId='123')
  self.assertEqual(len(candidates([item,item],'300308','2026-06-30','2026-10-05')),1)
  with self.assertRaises(ValueError):candidates([item,dict(item,adjunctUrl='finalpage/2026-08-22/124.PDF')],'300308','2026-06-30','2026-10-05')
 def test_invalid_time_not_date(self):
  item=dict(secCode='300308',announcementTitle='2026年半年度报告',announcementTime=True)
  with self.assertRaises(ValueError):candidates([item],'300308','2026-06-30','2026-10-05')
 def test_bad_company_structure_before_output(self):
  for spec in [None,{'companies':[None]}, {'companies':[{'code':True}]}]:
   with self.assertRaises(ValueError):run(spec,'unused-output')

class AnnualHistoricalWindowTests(unittest.TestCase):
 def test_april_annual_report_recheck_not_cut_off_in_march(self):
  from company_report_batch import collect_one
  from unittest.mock import patch
  import datetime as dt
  item=dict(secCode='600406',announcementTitle='2025年年度报告',announcementTime=int(dt.datetime(2026,4,28,tzinfo=dt.timezone.utc).timestamp()*1000),adjunctUrl='finalpage/2026-04-28/123.PDF',announcementId='123');calls=[]
  def fetch(url,data=None):
   if data is None:return b'%PDF fake'
   calls.append(data['seDate']);return json.dumps(dict(announcements=[item] if data['seDate'].endswith('2026-06-30') else [],hasMore=False)).encode()
  with tempfile.TemporaryDirectory() as d,patch('company_report_batch.parse_pdf',return_value=dict(pages=[],identityStatus='test')):
   r=collect_one('600406','2025-12-31','2026-10-06',Path(d)/'out',fetch=fetch)
   self.assertEqual(r['downloadStatus'],'downloaded');self.assertEqual(calls,['2025-12-31~2026-10-06','2025-12-31~2026-06-30'])

if __name__=='__main__':unittest.main()
