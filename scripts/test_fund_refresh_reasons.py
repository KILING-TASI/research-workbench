import unittest,tempfile
from pathlib import Path
from unittest.mock import patch
import portable_collect as p
from collection_quality_brief import brief
class FundRefreshReasons(unittest.TestCase):
 def seed(self,root):
  path=Path(root)/'research-data/fund/001938.json';path.parent.mkdir(parents=True);path.write_text('{bad','utf-8');return path
 def test_failed_refresh_retains_both_reasons(self):
  with tempfile.TemporaryDirectory() as root:
   path=self.seed(root)
   with patch.object(p,'get',side_effect=TimeoutError('网络超时')):b=p.collect(root,'fund',['001938'],'2026-09-30',True)
   row=b['rows'][0];self.assertTrue(row['cacheError']);self.assertTrue(row['refreshError']);self.assertIn('缓存不可用',row['errors']);self.assertIn('网络超时',row['errors']);self.assertEqual(path.read_text('utf-8'),'{bad');self.assertIn('网络超时',brief(b))
 def test_success_recovery_explained_not_failed(self):
  with tempfile.TemporaryDirectory() as root:
   self.seed(root);text='var fS_name="测试";var fS_code="001938";var Data_netWorthTrend=[{"x":1788192000000,"y":1}];'
   with patch.object(p,'get',return_value=text):b=p.collect(root,'fund',['001938'],'2026-09-30',True)
   row=b['rows'][0];self.assertIsNone(row['errors']);self.assertTrue(row['cacheError']);self.assertIn('本次已重新获取',brief(b));self.assertIsNone(row['refreshError'])
