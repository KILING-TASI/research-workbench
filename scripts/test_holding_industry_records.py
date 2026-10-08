import unittest,tempfile,hashlib
from pathlib import Path
from unittest.mock import patch
import test_report_screen_bridge as fixtures
from holding_industry_records import run,markdown
class Tests(unittest.TestCase):
 def test_dates_namespace_and_sources(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'raw';p.write_bytes(b'raw');ev=dict(path=str(p),sha256=hashlib.sha256(b'raw').hexdigest());report=fixtures.Tests().sample()
   base=dict(code='600519',industryCode='340301',includedAt='2025-01-01',updatedAt='2026-01-01',locator=dict(row=5))
   stocks=dict(rows=[base,dict(base,includedAt='2026-01-01')],sourceSha256=ev['sha256'],sourceUrl='https://example.org/stock')
   names=dict(entries=[dict(code='340301',name='白酒',locators=[dict(row=2)])],sourceSha256=ev['sha256'],sourceUrl='https://example.org/name')
   s=dict(asOf='2026-10-03',report=report,stockArchive=ev,codebook=ev)
   with patch('holding_industry_records.parse_stocks',return_value=stocks),patch('holding_industry_records.parse_names',return_value=names):
    r=run(s);self.assertEqual(len(r['rows'][0]['classificationRecords']),1);self.assertEqual(len(r['rows'][0]['recordsAfterReportDate']),1);self.assertIsNone(r['industryWeights']);self.assertIn('https://example.org/stock',markdown(r))
    report['holdings']['holdings'][0]['securityNamespace']='HK-equity';foreign=run(s)['rows'][0];self.assertEqual(foreign['classificationRecords'],[]);self.assertIn('不在境内分类覆盖范围',foreign['status'])
 def test_hash_mismatch_stops(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'raw';p.write_bytes(b'raw')
   with self.assertRaisesRegex(ValueError,'摘要'):run(dict(asOf='2026-10-03',report=fixtures.Tests().sample(),stockArchive=dict(path=str(p),sha256='wrong'),codebook={}))
 def test_input_shapes(self):
  for value in [[],{}, {'report':[], 'stockArchive':{}, 'codebook':{}}]:
   with self.assertRaisesRegex(ValueError,'资料对象'):run(value)
 def test_parsed_hash_must_match_selected_bytes(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'raw';p.write_bytes(b'raw');ev={'path':str(p),'sha256':hashlib.sha256(b'raw').hexdigest()}
   s={'asOf':'2026-10-03','report':fixtures.Tests().sample(),'stockArchive':ev,'codebook':ev}
   with patch('holding_industry_records.parse_stocks',return_value={'rows':[],'sourceSha256':'changed'}),patch('holding_industry_records.parse_names',return_value={'entries':[],'sourceSha256':ev['sha256']}):
    with self.assertRaisesRegex(ValueError,'摘要变化'):run(s)
if __name__=='__main__':unittest.main()
