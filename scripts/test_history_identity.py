import unittest,tempfile
from unittest.mock import patch
import market_collect as m
class HistoryIdentity(unittest.TestCase):
 def payload(self,name='样本ETF',date='2026-01-02'):
  return {'code':0,'data':{'sh512010':{'qt':{'sh512010':['1',name,'512010']},'day':[[date,'10','11','12','9','100']]}}}
 def test_backup_preserves_returned_name(self):
  ident={}
  with patch.object(m,'eastmoney_history',side_effect=ValueError('不可用')),patch.object(m,'fetch',return_value=self.payload()):m.history('512010','1','2026-01-01','2026-01-03',ident)
  self.assertEqual(ident['name'],'样本ETF');self.assertEqual(ident['verification'],'third-party-code-matched')
 def test_cross_year_conflict_does_not_publish_identity(self):
  ident={}
  with patch.object(m,'eastmoney_history',side_effect=ValueError('不可用')),patch.object(m,'fetch',side_effect=[self.payload('旧名','2025-12-31'),self.payload('新名','2026-01-02')]):
   with self.assertRaisesRegex(ValueError,'跨窗口'):m.history('512010','1','2025-12-31','2026-01-03',ident)
  self.assertEqual(ident,{})
 def test_primary_preserves_name(self):
  ident={}
  with patch.object(m,'fetch',return_value={'data':{'code':'512010','name':'样本ETF','klines':['2026-01-02,10,11,12,9,100,1000']}}):m.eastmoney_history('512010','1','2026-01-01','2026-01-03',ident)
  self.assertEqual(ident['code'],'512010')
 def test_identity_survives_cache_failure(self):
  def loader(code,market,start,end,identity):
   identity.update(code=code,name='样本ETF',verification='third-party-code-matched');return [{'date':'2026-01-02','open':10,'close':11,'high':12,'low':9}],['https://example.org/data']
  with tempfile.TemporaryDirectory() as root,patch.object(m,'fund_announcements',side_effect=ValueError('缺口')):
   with patch.object(m,'history',side_effect=loader):first=m.collect_market(root,'etf','512010','2026-01-03',True,'2026-01-01')
   with patch.object(m,'history',side_effect=TimeoutError()):second=m.collect_market(root,'etf','512010','2026-01-03',True,'2026-01-01')
   self.assertEqual(first['identity'],second['identity']);self.assertEqual(second['components']['history']['status'],'cached-after-failure')
