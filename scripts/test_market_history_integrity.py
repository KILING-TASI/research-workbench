import unittest
from unittest.mock import patch
import market_collect as m
class Tests(unittest.TestCase):
 def payload(self,code='512010',high='12',volume='100'):
  return {'code':0,'data':{'sh512010':{'qt':{'sh512010':['1','ETF',code]},'day':[['2026-01-02','10','11',high,'9',volume]]}}}
 def test_backup_identity_and_ohlc(self):
  with patch.object(m,'eastmoney_history',side_effect=ValueError('primary unavailable')),patch.object(m,'fetch',return_value=self.payload()):
   self.assertEqual(m.history('512010','1','2026-01-01','2026-01-03')[0][0]['close'],11)
  for p in [self.payload(code='512170'),self.payload(high='10'),self.payload(volume='-1')]:
   with patch.object(m,'eastmoney_history',side_effect=ValueError('primary unavailable')),patch.object(m,'fetch',return_value=p):
    with self.assertRaises(ValueError):m.history('512010','1','2026-01-01','2026-01-03')
 def test_primary_rejects_bad_price_and_amount(self):
  for line in ['2026-01-02,10,11,10,9,100,1000','2026-01-02,10,11,12,9,100,-1']:
   with patch.object(m,'fetch',return_value={'data':{'code':'512010','klines':[line]}}):
    with self.assertRaises(ValueError):m.eastmoney_history('512010','1','2026-01-01','2026-01-03')
