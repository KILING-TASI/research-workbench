import tempfile,unittest,urllib.error
from pathlib import Path
from unittest.mock import patch
from download_issuance_originals import download,select
class Downloads(unittest.TestCase):
 def snapshot(self):return {'records':[{'code':'1','name':'A','applyDate':'2026-10-01','announcements':[{'title':'发行公告','date':'2026-09-20','url':'https://static.cninfo.com.cn/finalpage/2026-09-20/1.PDF'},{'title':'发行结果公告','date':'2026-09-25','url':'https://static.cninfo.com.cn/finalpage/2026-09-25/2.PDF'}]}]}
 def test_access_limit_stops(self):
  with tempfile.TemporaryDirectory() as t,patch('download_issuance_originals.urllib.request.urlopen',side_effect=urllib.error.HTTPError('u',403,'blocked',None,None)) as request:
   r=download(self.snapshot(),Path(t)/'new')
   self.assertEqual(request.call_count,1);self.assertTrue(r['accessLimitStopped'])
   self.assertEqual(r['details'][1]['status'],'not-attempted')
 def test_does_not_guess_urls(self):
  s=self.snapshot();s['records'][0]['announcements']=[{'title':'发行公告','url':'https://example.com/a.pdf'}]
  docs,missing=select(s);self.assertFalse(docs);self.assertEqual(len(missing),2)
 def test_same_date_notice_not_full_document(self):
  s=self.snapshot();s['records'][0]['announcements']=[
   {'title':t,'date':'2026-09-20','url':f'https://static.cninfo.com.cn/finalpage/2026-09-20/{i}.PDF'}
   for i,t in enumerate(['发行公告','发行公告（更正公告）','发行公告（更正后）'],1)]
  docs,missing=select(s)
  self.assertTrue(docs[0]['sourceUrl'].endswith('/3.PDF'))
  self.assertTrue(docs[0]['versionReviewRequired'])
  self.assertTrue(any(m['status']=='correction-notice-needs-body-comparison' for m in missing))
 def test_notice_only_does_not_substitute_full_document(self):
  s=self.snapshot();s['records'][0]['announcements']=[{'title':'发行结果更正公告','date':'2026-09-20','url':'https://static.cninfo.com.cn/finalpage/2026-09-20/4.PDF'}]
  docs,missing=select(s);self.assertFalse(docs)
  self.assertTrue(any(m['status']=='no-supported-original-link' and m['kind']=='result' for m in missing))
if __name__=='__main__':unittest.main()
