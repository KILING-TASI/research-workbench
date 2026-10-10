import unittest
import subprocess
from unittest.mock import patch
from environment_check import inspect,markdown
class Tests(unittest.TestCase):
 def test_single_demo_check_never_probes_unused_tools(self):
  with patch('specialist_loader.check',side_effect=AssertionError('unused tool')),patch('environment_check.subprocess.run') as process:
   result=inspect(entry='demo')
   self.assertTrue(result['available']);self.assertEqual(result['dataStatus'],'not-checked')
   self.assertIsNone(result['specialistDependency']);process.assert_not_called()
 def test_single_cashflow_check_reports_missing_tool_not_missing_data(self):
  from specialist_loader import SpecialistUnavailableError
  with patch('specialist_loader.location',side_effect=SpecialistUnavailableError('独立工具不可用')),patch('environment_check.subprocess.run') as process:
   result=inspect(entry='cashflow')
   self.assertFalse(result['available']);self.assertEqual(result['dataStatus'],'not-checked')
   self.assertIn('portfolio-decision-engine',markdown(result));process.assert_not_called()
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
 def test_optional_repair_uses_distribution_name_not_import_name(self):
  with patch('environment_check.importlib.util.find_spec',return_value=None),patch('environment_check.shutil.which',return_value=None):
   rows={x['component']:x for x in inspect()['dependencies']}
   self.assertEqual(rows['docx']['installCommand'],'python -m pip install python-docx')
   self.assertEqual(rows['numpy']['installCommand'],'python -m pip install numpy')
   self.assertNotIn('installCommand',rows['@oai/artifact-tool'])
 def test_invalid_optional_component_path_does_not_block_basic_checks(self):
  with patch('environment_check.component_environment',side_effect=ValueError('目录不存在')),patch('environment_check.shutil.which',return_value=None):
   rows={x['component']:x for x in inspect()['dependencies']}
   self.assertTrue(rows['python-runtime']['available'])
   self.assertFalse(rows['@oai/artifact-tool']['available'])
   self.assertIn('配置无效',rows['@oai/artifact-tool']['status'])
if __name__=='__main__':unittest.main()
