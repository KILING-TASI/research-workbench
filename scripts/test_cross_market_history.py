import unittest,json,tempfile
from pathlib import Path
from cross_market_history import parse,mapped_symbol,collect,write_result
class Tests(unittest.TestCase):
 def test_duplicate_json_is_not_history_success(self):
  result,attempts=collect('HK','00700','2026-01-01','2026-01-03',lambda u:b'{"code":0,"code":1,"data":{}}')
  self.assertEqual(result['status'],'历史未取得');self.assertTrue(attempts[0]['sha256'])
 def test_untyped_code_and_compact_date_rejected(self):
  from cross_market_quote import symbol
  with self.assertRaises(ValueError):symbol('HK',700)
  with self.assertRaises(ValueError):parse(self.sample(),'HK','00700','20260101','2026-01-03')
 def sample(self):return dict(code=0,data={'hk00700':dict(qt={'hk00700':['100','腾讯','00700']},day=[['2026-01-02','10','11','12','9']])})
 def test_hk(self):self.assertEqual(parse(self.sample(),'HK','00700','2026-01-01','2026-01-03')['history'][0]['close'],11)
 def test_timeout_leaves_gap_and_artifacts(self):
  def failed(url):raise TimeoutError('timeout')
  r,a=collect('HK','00700','2026-01-01','2026-01-03',failed)
  self.assertFalse(r['history']);self.assertIsNone(r['sha256']);self.assertIn('TimeoutError',r['reason'])
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'r.json';write_result(r,a,p);self.assertTrue(p.with_suffix('.md').exists());self.assertTrue(p.with_suffix('.raw.json').exists())
 def test_bad_json_keeps_body(self):
  r,a=collect('HK','00700','2026-01-01','2026-01-03',lambda u:b'<html>error</html>')
  self.assertFalse(r['history']);self.assertIn('<html>',a[0]['rawText']);self.assertTrue(r['sha256'])
 def test_mapping_failure_does_not_attach_initial_hash(self):
  calls=[]
  def fetch(url):
   calls.append(url)
   if len(calls)>1:raise TimeoutError('mapped unavailable')
   return json.dumps(dict(code=0,data={'usAAPL':dict(day=[],qt={'usAAPL':['delay','苹果','AAPL.OQ']})})).encode()
  r,a=collect('US','AAPL','2026-01-01','2026-01-03',fetch)
  self.assertEqual(r['attemptCount'],2);self.assertIsNone(r['sha256']);self.assertTrue(a[0]['sha256']);self.assertEqual(r['querySymbol'],'usAAPL.OQ')
 def test_success_collect(self):
  r,a=collect('HK','00700','2026-01-01','2026-01-03',lambda u:json.dumps(self.sample()).encode())
  self.assertEqual(r['currency'],'HKD');self.assertEqual(r['startGapDays'],1)
 def test_empty(self):
  s=self.sample();s['data']['hk00700']['day']=[]
  with self.assertRaises(ValueError):parse(s,'HK','00700','2026-01-01','2026-01-03')
 def test_ohlc(self):
  s=self.sample();s['data']['hk00700']['day'][0][3]='8'
  with self.assertRaises(ValueError):parse(s,'HK','00700','2026-01-01','2026-01-03')
 def test_vendor_mapping(self):
  s=dict(code=0,data={'usAAPL':dict(day=[],qt={'usAAPL':['delay','苹果','AAPL.OQ']})});self.assertEqual(mapped_symbol(s,'US','AAPL'),'usAAPL.OQ')
 def test_no_guess_mapping(self):
  s=dict(code=0,data={'usAAPL':dict(day=[],qt={'usAAPL':['delay','苹果','MSFT.OQ']})});self.assertIsNone(mapped_symbol(s,'US','AAPL'))
 def test_mapped_parse(self):
  s=dict(code=0,data={'usAAPL.OQ':dict(day=[['2026-01-02','10','11','12','9']],qt={'usAAPL.OQ':['delay','苹果','AAPL.OQ']})});self.assertEqual(parse(s,'US','AAPL','2026-01-01','2026-01-03','usAAPL.OQ')['currency'],'USD')
if __name__=='__main__':unittest.main()
