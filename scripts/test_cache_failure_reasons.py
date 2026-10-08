import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
import market_collect as m
class CacheFailureReasons(unittest.TestCase):
 def seed(self,root):
  p=Path(root)/'research-data/etf/512010-1/history-2026-01-01-2026-01-03.json';p.parent.mkdir(parents=True);p.write_text('{bad','utf-8');return p
 def loader(self,*args):return [{'date':'2026-01-02','open':10,'close':11,'high':12,'low':9}],['https://example.org/data']
 def test_both_causes_preserved_without_corrupt_cache_reuse(self):
  with tempfile.TemporaryDirectory() as root:
   p=self.seed(root)
   with patch.object(m,'history',side_effect=TimeoutError('网络超时')),patch.object(m,'fund_announcements',side_effect=TimeoutError()):out=m.collect_market(root,'etf','512010','2026-01-03',True,'2026-01-01')
   c=out['components']['history'];self.assertEqual(c['status'],'failed');self.assertIn('缓存不可用',c['error']);self.assertIn('网络超时',c['error']);self.assertTrue(c['cacheError']);self.assertTrue(c['refreshError']);self.assertEqual(p.read_text('utf-8'),'{bad');self.assertEqual(out['history'],[])
 def test_success_after_corrupt_cache_not_reported_failed(self):
  with tempfile.TemporaryDirectory() as root:
   self.seed(root)
   with patch.object(m,'history',side_effect=self.loader),patch.object(m,'fund_announcements',side_effect=TimeoutError()):out=m.collect_market(root,'etf','512010','2026-01-03',True,'2026-01-01')
   c=out['components']['history'];self.assertEqual(c['status'],'success');self.assertIsNone(c['error']);self.assertTrue(c['cacheError']);self.assertIsNone(c['refreshError']);self.assertNotIn('history',out['errors'])
