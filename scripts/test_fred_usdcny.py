import unittest
from fred_usdcny import parse
class Tests(unittest.TestCase):
 def test_missing_or_extra_csv_column_rejected(self):
  for body in [b'2026-01-01\n',b'2026-01-01,7,extra\n']:
   with self.assertRaises(ValueError):parse(b'observation_date,DEXCHUS\n'+body,'2026-01-01','2026-01-03','2026-10-03')
 def test_missing_not_filled(self):
  r=parse(b'observation_date,DEXCHUS\n2026-01-01,7.0\n2026-01-02,\n2026-01-03,6.9\n','2026-01-01','2026-01-03','2026-10-03');self.assertEqual(len(r['history']),2);self.assertEqual(r['missingObservationDates'],['2026-01-02']);self.assertFalse(r['historicalPublicationVerified'])
 def test_wrong_series_rejected(self):
  with self.assertRaises(ValueError):parse(b'observation_date,OTHER\n','2026-01-01','2026-01-03','2026-10-03')
 def test_invalid_or_duplicate_rejected(self):
  for body in [b'2026-01-01,NaN\n',b'2026-01-01,7\n2026-01-01,7\n']:
   with self.assertRaises(ValueError):parse(b'observation_date,DEXCHUS\n'+body,'2026-01-01','2026-01-03','2026-10-03')
if __name__=='__main__':unittest.main()
