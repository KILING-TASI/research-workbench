import unittest
from series_frequency import inspect
class Tests(unittest.TestCase):
 def test_daily(self):self.assertTrue(inspect(['2025-01-02','2025-01-03','2025-01-06'])['dailyAnnualizationAllowed'])
 def test_monthly(self):self.assertFalse(inspect(['2025-01-01','2025-02-01','2025-03-01'])['dailyAnnualizationAllowed'])
 def test_large_missing_gap(self):self.assertFalse(inspect(['2025-01-01','2025-01-02','2025-01-03','2025-02-03'])['dailyAnnualizationAllowed'])
 def test_too_short(self):self.assertFalse(inspect(['2025-01-01','2025-01-02'])['dailyAnnualizationAllowed'])
if __name__=='__main__':unittest.main()
