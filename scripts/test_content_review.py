import unittest
from company_financial_report import extreme_ratio_note
from environment_check import inspect
from unittest.mock import patch
class Tests(unittest.TestCase):
 def test_extreme_ratio_does_not_imply_cause(self):
  self.assertIsNotNone(extreme_ratio_note([-164.4325]))
  self.assertIsNotNone(extreme_ratio_note([10]))
  self.assertIsNone(extreme_ratio_note([None,.95,-.3]))
 def test_openpyxl_not_financial_export_dependency(self):
  with patch('environment_check.shutil.which',return_value=None):
   rows={r['component']:r for r in inspect()['dependencies']}
  self.assertIn('不替代财务底稿',str(rows['openpyxl']['features']))
  self.assertIn('@oai/artifact-tool',rows)
if __name__=='__main__':unittest.main()
