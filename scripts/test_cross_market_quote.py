import unittest
from cross_market_quote import parse,symbol
class Tests(unittest.TestCase):
 def raw(self,market='HK',code='00700',stamp='2026/10/02 16:08:10',price='421.2'):
  f=['0']*37;f[1]='腾讯';f[2]=code;f[3]=price;f[30]=stamp;return 'v_'+symbol(market,code)+'="'+'~'.join(f)+'";'
 def test_hk(self):self.assertEqual(parse(self.raw(),'HK','00700','2026-10-03')['quote']['currency'],'HKD')
 def test_us(self):self.assertEqual(parse(self.raw('US','AAPL','2026-10-02 16:00:01'),'US','AAPL','2026-10-03')['quote']['currency'],'USD')
 def test_future_isolated(self):self.assertIsNone(parse(self.raw(),'HK','00700','2026-10-01')['quote'])
 def test_identity(self):
  with self.assertRaises(ValueError):parse(self.raw(code='00701'),'HK','00700','2026-10-03')
 def test_invalid_price(self):
  with self.assertRaises(ValueError):parse(self.raw(price='nan'),'HK','00700','2026-10-03')
if __name__=='__main__':unittest.main()
