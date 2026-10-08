import unittest
from fred_hkdcny import derive
class Tests(unittest.TestCase):
 def test_bad_csv_columns_not_ignored(self):
  for row in ['2026-01-01','2026-01-01,7.8,extra']:
   with self.subTest(row=row),self.assertRaises(ValueError):derive(self.usd(),('observation_date,DEXHKUS\n'+row+'\n').encode(),'2026-01-01','2026-01-03','2026-10-03')
 def usd(self):return dict(unit='CNY-per-USD',baseCurrency='USD',targetCurrency='CNY',sourceUrl='https://fred.stlouisfed.org/series/DEXCHUS',history=[dict(date='2026-01-01',value=7),dict(date='2026-01-02',value=7.1),dict(date='2026-01-03',value=7.2)])
 def test_direction_and_missing(self):
  r=derive(self.usd(),b'observation_date,DEXHKUS\n2026-01-01,7.8\n2026-01-02,\n2026-01-03,8\n','2026-01-01','2026-01-03','2026-10-03');self.assertAlmostEqual(r['history'][0]['value'],7/7.8);self.assertEqual(r['unmatchedUSDCDates'],['2026-01-02'])
 def test_wrong_direction(self):
  u=self.usd();u['unit']='USD-per-CNY'
  with self.assertRaises(ValueError):derive(u,b'','2026-01-01','2026-01-03','2026-10-03')
 def test_duplicate_or_wrong_series(self):
  for raw in [b'observation_date,OTHER\n',b'observation_date,DEXHKUS\n2026-01-01,7\n2026-01-01,7\n']:
   with self.assertRaises(ValueError):derive(self.usd(),raw,'2026-01-01','2026-01-03','2026-10-03')
if __name__=='__main__':unittest.main()
