import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
import portable_collect as p
class PortableCacheDigest(unittest.TestCase):
 def seed(self,root):
  text='var fS_name="测试";var fS_code="001938";var Data_netWorthTrend=[{"x":1788192000000,"y":1,"unitMoney":""}];'
  with patch.object(p,'get',return_value=text):p.collect(root,'fund',['001938'],'2026-09-30',True)
  return Path(root)/'research-data/fund/001938.json'
 def test_tampered_content_or_missing_digest_not_reused(self):
  for field in ['nav','name','source','distribution','digest']:
   with self.subTest(field=field),tempfile.TemporaryDirectory() as root:
    path=self.seed(root);d=json.loads(path.read_text('utf-8'))
    if field=='nav':d['history'][0]['nav']=2
    elif field=='name':d['identity']['name']='另一基金'
    elif field=='source':d['source']='https://example.org/other'
    elif field=='distribution':d['history'][0]['distribution']='分红：每份派现金1元'
    else:d.pop('contentSha256')
    path.write_text(json.dumps(d),'utf-8');before=path.read_bytes();row=p.collect(root,'fund',['001938'],'2026-09-30',False)['rows'][0]
    self.assertEqual(row['history'],[]);self.assertIn('摘要',row['errors']);self.assertEqual(path.read_bytes(),before)
 def test_valid_cache_reused_without_fetch(self):
  with tempfile.TemporaryDirectory() as root:
   path=self.seed(root);old=json.loads(path.read_text('utf-8'))
   with patch.object(p,'get') as fetch:row=p.collect(root,'fund',['001938'],'2026-09-30',False)['rows'][0]
   fetch.assert_not_called();self.assertIsNone(row['errors']);self.assertEqual(row['retrievedAt'],old['retrievedAt']);self.assertEqual(row['history'],old['history'])

 def test_duplicate_identity_cache_rejected_and_preserved(self):
  with tempfile.TemporaryDirectory() as root:
   path=self.seed(root);text=path.read_text('utf-8');path.write_text(text.replace('{','{"code":"999999",',1),'utf-8');before=path.read_bytes()
   row=p.collect(root,'fund',['001938'],'2026-09-30',False)['rows'][0]
   self.assertEqual(row['history'],[]);self.assertIsNotNone(row['cacheError']);self.assertEqual(path.read_bytes(),before)
 def test_overflow_json_in_source_not_accepted(self):
  with self.assertRaises(ValueError):p.named('var payload={"amount":1e999};','payload')
