import unittest,subprocess
from unittest.mock import patch
from environment_check import inspect
class FinancialExportDependency(unittest.TestCase):
 def check(self,response):
  with patch('environment_check.importlib.util.find_spec',return_value=None),patch('environment_check.shutil.which',return_value='node'),patch('environment_check.subprocess.run',side_effect=[subprocess.CompletedProcess([],0,'v22.0.0',''),subprocess.CompletedProcess([],0,response,'')]):return {r['component']:r for r in inspect()['dependencies']}
 def test_node_exists_missing_export_component_separate(self):
  rows=self.check('{"found":false}');self.assertTrue(rows['node']['available']);self.assertFalse(rows['@oai/artifact-tool']['available']);self.assertIn('HTML和JSON',rows['@oai/artifact-tool']['status'])
 def test_component_found_not_claiming_workbook_accepted(self):
  row=self.check('{"found":true}')['@oai/artifact-tool'];self.assertTrue(row['available']);self.assertIn('尚未验证加载',row['status'])
 def test_bad_probe_not_reported_available(self):
  row=self.check('{"found":"true"}')['@oai/artifact-tool'];self.assertFalse(row['available']);self.assertIn('未确认',row['status'])
