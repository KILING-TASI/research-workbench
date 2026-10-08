import json,tempfile,unittest,hashlib
from pathlib import Path
from unittest.mock import patch
from holdings_snapshot_review import run,security_label
class Tests(unittest.TestCase):
 def test_ambiguous_json_rejected_before_output(self):
  from holdings_snapshot_review import read_json
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory)/'input.json'
   for text in ['{"weight":1,"weight":2}','{"weight":1e999}']:
    p.write_text(text)
    with self.assertRaises(ValueError):read_json(p)
 def check_changed_field(self,field,value):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);pdf=p/'original.pdf';pdf.write_bytes(b'fixture');sha=hashlib.sha256(pdf.read_bytes()).hexdigest()
   row=dict(securityNamespace='CN-equity',code='600519',name='example',weight=.5,marketValueCNY=50)
   fund=dict(id='000001',reportDate='2026-06-30',publishedAt='2026-08-31',sourceSha256=sha,sourceUrl='https://example.org/report',holdings=[row],equityWeight=.5,netAssetsCNY=100,equityMarketValueCNY=50)
   archive=dict(code='000001',reportDate=fund['reportDate'],asOf='2026-10-05',documentPath=str(pdf),sha256=sha,metadata=dict(sourceUrl=fund['sourceUrl'],title='example fund report',publishedAt=fund['publishedAt']))
   (p/'archive.json').write_text(json.dumps(archive));data=dict(asOf='2026-10-05',funds=[fund]);(p/'input.json').write_text(json.dumps(data));parsed=json.loads(json.dumps(fund));parsed['holdings'][0][field]=value
   with patch('holdings_snapshot_review.inspect_and_parse',return_value=parsed),patch('holdings_snapshot_review.subprocess.run') as calc:
    with self.assertRaisesRegex(ValueError,'重新解析'):run(dict(holdingsPath=str(p/'input.json'),reportPaths={'000001':str(p/'archive.json')}),p/'out')
    self.assertFalse((p/'out').exists());calc.assert_not_called()
 def test_changed_weight_blocked(self):self.check_changed_field('weight',.4)
 def test_changed_quantity_blocked(self):self.check_changed_field('quantity',500)
 def test_changed_locator_blocked(self):self.check_changed_field('locator','PDF页99')
 def test_changed_component_page_blocked(self):self.check_changed_field('components',[dict(locator='PDF页99')])
 def test_display_same_code_different_market(self):
  a=dict(code='123456',market='SSE',shareClass='ordinary',name='境内公司')
  b=dict(code='123456',market='HKEX',shareClass='ordinary',name='香港公司')
  self.assertIn('境内公司',security_label({'holdings':[a,b]},a))
  self.assertIn('香港公司',security_label({'holdings':[a,b]},b))
 def test_display_duplicate_identity_rejected(self):
  row=dict(code='123456',market='SSE',shareClass='ordinary',name='公司')
  with self.assertRaises(ValueError):security_label({'holdings':[row,row]},row)
 def test_display_confirmed_namespace_matches_unresolved_exchange(self):
  row=dict(code='600519',market='SSE',securityNamespace='CN-equity',shareClass='ordinary',name='公司')
  common=dict(row,market='CN-exchange-unresolved')
  self.assertIn('上海',security_label({'holdings':[row]},common))
 def test_missing_metadata_rejected_before_parse_and_output(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);pdf=root/'original.pdf';pdf.write_bytes(b'fixture')
   fund=dict(id='000001');(root/'holdings.json').write_text(json.dumps({'funds':[fund]}))
   (root/'archive.json').write_text(json.dumps({'documentPath':str(pdf),'metadata':{'sourceUrl':'https://example.org/report'}}))
   with patch('holdings_snapshot_review.inspect_and_parse') as parse:
    with self.assertRaisesRegex(ValueError,'title,publishedAt'):run(dict(holdingsPath=str(root/'holdings.json'),reportPaths={'000001':str(root/'archive.json')}),root/'report')
    parse.assert_not_called();self.assertFalse((root/'report').exists())
if __name__=='__main__':unittest.main()
