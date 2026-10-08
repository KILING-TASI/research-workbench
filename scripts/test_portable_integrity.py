import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
import portable_collect as p
import batch_collect as b
import research_pipeline as r

class Tests(unittest.TestCase):
 def test_compact_date_rejected(self):
  with tempfile.TemporaryDirectory() as root,patch.object(p,'get') as get:
   with self.assertRaises(ValueError):p.collect(root,'fund',['001938'],'20260930',True)
   get.assert_not_called();self.assertFalse((Path(root)/'research-data').exists())
  with self.assertRaises(ValueError):b.run('.',{'asOf':'20260930','requests':[]},None)
 def test_corrupt_or_wrong_identity_cache_not_reused(self):
  for text in ['{broken',json.dumps({'code':'999999','kind':'fund','history':[],'retrievedAt':'x'})]:
   with tempfile.TemporaryDirectory() as root:
    file=Path(root)/'research-data/fund/001938.json';file.parent.mkdir(parents=True);file.write_text(text,encoding='utf-8')
    row=p.collect(root,'fund',['001938'],'2026-09-30',False)['rows'][0]
    self.assertEqual(row['history'],[]);self.assertIn('缓存不可用',row['errors'])
 def test_invalid_vendor_observation_keeps_old_cache(self):
  with tempfile.TemporaryDirectory() as root:
   file=Path(root)/'research-data/fund/001938.json';file.parent.mkdir(parents=True)
   old={'code':'001938','kind':'fund','history':[{'date':'2026-09-01','nav':1}],'retrievedAt':'2026-09-01T00:00:00+00:00'};old['contentSha256']=p.cache_hash(old);file.write_text(json.dumps(old),encoding='utf-8');before=file.read_bytes()
   text='var fS_name="测试";var fS_code="001938";var Data_netWorthTrend=[{"x":1788192000000,"y":0}];'
   with patch.object(p,'get',return_value=text):row=p.collect(root,'fund',['001938'],'2026-09-30',True)['rows'][0]
   self.assertTrue(row['cacheRetained']);self.assertEqual(file.read_bytes(),before);self.assertIn('无效净值',row['errors'])
 def test_invalid_distributions_rejected(self):
  for value in ['分红：每份派现金1..2元',123,'分红：每份派现金'+('9'*400)+'元']:
   with self.subTest(value=str(value)[:20]),self.assertRaises(ValueError):r.series([{'date':'2026-09-01','nav':1,'distribution':value}],'2026-09-30','nav-with-distributions')
 def test_metric_overflow_rejected(self):
  with self.assertRaisesRegex(ValueError,'溢出'):r.metrics([1e-300,1e300])

if __name__=='__main__':unittest.main()
