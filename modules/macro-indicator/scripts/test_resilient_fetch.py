import unittest,urllib.error
from unittest.mock import Mock,MagicMock,patch
from resilient_fetch import get_text,FetchError
class BoundedOfficialFetch(unittest.TestCase):
 def response(self,raw):
  r=MagicMock();r.__enter__.return_value=r;r.read.return_value=raw;return r
 def test_access_denied_and_rate_limit_not_retried(self):
  for status in [403,429]:
   opener=Mock(side_effect=urllib.error.HTTPError('https://example.org',status,'blocked',{},None));sleep=Mock();metrics={}
   with self.assertRaises(FetchError) as raised:get_text('https://example.org',opener=opener,sleeper=sleep,metrics=metrics)
   self.assertEqual(raised.exception.attempts,1);sleep.assert_not_called();self.assertFalse(metrics['retryable'])
 def test_timeout_then_success_records_attempts(self):
  opener=Mock(side_effect=[TimeoutError(),self.response(b'body')]);sleep=Mock();metrics={}
  self.assertEqual(get_text('https://example.org',opener=opener,sleeper=sleep,metrics=metrics),'body');self.assertEqual(metrics['attempts'],2);sleep.assert_called_once_with(1)
 def test_invalid_encoding_not_retried(self):
  opener=Mock(return_value=self.response(b'\xff'));sleep=Mock()
  with self.assertRaises(FetchError):get_text('https://example.org',opener=opener,sleeper=sleep)
  self.assertEqual(opener.call_count,1);sleep.assert_not_called()

 def test_large_response_not_retried(self):
  opener=Mock(return_value=self.response(b'x'*(8*1024*1024+1)));sleep=Mock()
  with self.assertRaises(FetchError):get_text('https://example.org',opener=opener,sleeper=sleep)
  self.assertEqual(opener.call_count,1);sleep.assert_not_called()

class PbcSameDaySources(unittest.TestCase):
 def notice(self,rate):
  return '<div id="shijian">2026-10-08</div><div id="zoom">2026年10月8日开展逆回购。<table><tr><td>期限</td><td>操作利率</td></tr><tr><td>7天</td><td>'+rate+'%</td></tr></table></div>'
 def run_fetch(self,rates,metrics):
  import pbc_repo
  urls=['https://www.pbc.gov.cn/zhengcehuobisi/125475/'+str(i)+'.html' for i in range(len(rates))]
  pages={url:self.notice(rate) for url,rate in zip(urls,rates)}
  pages[pbc_repo.INDEX]=''.join('<a href="'+url+'">公开市场业务交易公告</a>' for url in urls)
  with patch('pbc_repo.get_text',side_effect=lambda url,**kwargs:pages[url]):return pbc_repo.fetch('2026-10-08',metrics)
 def test_conflicting_rates_preserve_candidates_and_reject_merge(self):
  metrics={}
  with self.assertRaisesRegex(ValueError,'冲突'):self.run_fetch(['1.4','1.5'],metrics)
  self.assertEqual(len(metrics['conflicts'][0]['candidates']),2)
 def test_matching_duplicate_sources_remain_traceable(self):
  rows=self.run_fetch(['1.4','1.40'],{})
  self.assertEqual(len(rows),1);self.assertEqual(len(rows[0]['matchingSources']),2)
