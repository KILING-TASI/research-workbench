import unittest
from fund_comparison_brief import recovery_observation,monthly_observation

class Recovery(unittest.TestCase):
 def test_months_use_previous_endpoint_and_skip_missing_month(self):
  rows=monthly_observation(['2025-01-15','2025-01-31','2025-02-28','2025-04-30'],[1,1.1,1.21,1.3])
  self.assertEqual(rows[0]['scope'],'first-month-partial')
  self.assertAlmostEqual(rows[1]['returnPct'],10)
  self.assertIsNone(rows[2]['returnPct']);self.assertEqual(rows[2]['scope'],'missing-previous-month')
 def test_repaired_and_unrepaired_paths(self):
  dates=['2025-01-01','2025-01-02','2025-01-04','2025-01-08']
  result=recovery_observation(dates,[1,.8,.9,1])
  self.assertEqual(result['recoveryDate'],'2025-01-08');self.assertEqual(result['underwaterCalendarDays'],7)
  result=recovery_observation(dates,[1,.8,.9,.95])
  self.assertIsNone(result['recoveryDate']);self.assertEqual(result['status'],'not-recovered-by-window-end')
 def test_deeper_later_episode_and_no_drawdown(self):
  dates=['2025-01-01','2025-01-02','2025-01-03','2025-01-04']
  result=recovery_observation(dates,[1,.9,1.2,.8])
  self.assertEqual(result['peakDate'],'2025-01-03');self.assertEqual(result['troughDate'],'2025-01-04')
  self.assertEqual(recovery_observation(dates,[1,1,1.1,1.2])['status'],'no-observed-drawdown')
