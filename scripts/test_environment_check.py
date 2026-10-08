import unittest
import subprocess
from unittest.mock import patch
from environment_check import inspect,markdown
class Tests(unittest.TestCase):
 def test_empty_node_version_is_not_available(self):
  with patch('environment_check.importlib.util.find_spec',return_value=None),patch('environment_check.shutil.which',return_value='node'),patch('environment_check.subprocess.run',return_value=subprocess.CompletedProcess([],0,'','')) as process:
   rows={x['component']:x for x in inspect()['dependencies']}
   self.assertFalse(rows['node']['available']);self.assertFalse(rows['@oai/artifact-tool']['available']);self.assertEqual(process.call_count,1)
 def test_missing_excel_dependencies_listed_without_install(self):
  with patch('environment_check.importlib.util.find_spec',return_value=None),patch('environment_check.shutil.which',return_value=None),patch('environment_check.subprocess.run') as process:
   r=inspect();rows={x['component']:x for x in r['dependencies']}
   self.assertFalse(rows['xlrd']['available']);self.assertFalse(rows['openpyxl']['available']);self.assertIn('申万新版行业代码表',markdown(r));process.assert_not_called()
 def test_found_module_does_not_claim_acceptance(self):
  with patch('environment_check.importlib.util.find_spec',return_value=object()),patch('environment_check.shutil.which',return_value=None):
   r=inspect();self.assertIn('尚未证明实际计算通过',r['dependencies'][0]['status'])
if __name__=='__main__':unittest.main()
