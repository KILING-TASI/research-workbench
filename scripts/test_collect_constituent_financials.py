import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from collect_constituent_financials import collect

class Tests(unittest.TestCase):
 def test_invalid_pages_do_not_create_output(self):
  with tempfile.TemporaryDirectory() as root:
   path=Path(root)/'input.json';path.write_text(json.dumps(self.spec()),'utf-8');out=Path(root)/'out.json'
   for pages in [True,0,11,'1']:
    blob=json.dumps(dict(result=dict(pages=pages,data=[dict(SECURITY_CODE='000001')]))).encode()
    with patch('collect_constituent_financials.download',return_value=blob),self.assertRaises(ValueError):collect(path,out,'2026-06-30')
    self.assertFalse(out.exists())
 def spec(self):return dict(asOf='2026-09-30',current=dict(constituents=dict(value=[dict(code='000001')])),candidate=dict(constituents=dict(value=[dict(code='000002')])))
 def test_partial_codes_are_explicit(self):
  with tempfile.TemporaryDirectory() as root:
   path=Path(root)/'input.json';path.write_text(json.dumps(self.spec()),'utf-8');out=Path(root)/'out.json'
   blob=json.dumps(dict(result=dict(pages=1,data=[dict(SECURITY_CODE='000001',CURRENCY='CNY',REPORT_DATE='2026-06-30',NOTICE_DATE='2026-08-31')]))).encode()
   with patch('collect_constituent_financials.download',return_value=blob):result=collect(path,out,'2026-06-30')
   self.assertEqual(result['missingCodes'],['000002']);self.assertEqual(json.loads(out.read_text('utf-8'))['coverageStatus'],'partial')
 def test_future_period_rejected_before_network(self):
  with tempfile.TemporaryDirectory() as root:
   path=Path(root)/'input.json';path.write_text(json.dumps(self.spec()),'utf-8')
   with patch('collect_constituent_financials.download') as fetch,self.assertRaises(ValueError):collect(path,Path(root)/'out.json','2026-12-31')
   fetch.assert_not_called()

if __name__=='__main__':unittest.main()
