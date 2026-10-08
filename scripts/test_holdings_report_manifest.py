import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
import test_archive_holdings as fixture_module
from archive_holdings import run
from verify_collection_report import verify
class HoldingsReportManifest(unittest.TestCase):
 def fixture(self,root):
  source,pdf=fixture_module.ArchiveHoldings().fixture(root);out=Path(root)/'report'
  with patch('archive_holdings.read_pages',return_value=[(1,'报告 159869 本报告期自2026年1月1日至6月30日止。')]):run(source,out,parse_fn=lambda *args:(_ for _ in ()).throw(ValueError('布局缺口')))
  return source,pdf,out
 def test_input_original_and_report_checked_separately(self):
  with tempfile.TemporaryDirectory() as root:
   source,pdf,out=self.fixture(root);r=verify(out/'report-manifest.json',source,pdf)
   self.assertEqual(r['status'],'stored-content-verified');self.assertTrue(r['originalMatches']);self.assertEqual(r['sourceVerification'],'not-verified')
   pdf.write_bytes(b'changed');self.assertEqual(verify(out/'report-manifest.json',source,pdf)['status'],'content-mismatch')
 def test_result_json_change_detected(self):
  with tempfile.TemporaryDirectory() as root:
   source,pdf,out=self.fixture(root);(out/'result.json').write_text('{}','utf-8');self.assertEqual(verify(out/'report-manifest.json',source)['status'],'content-mismatch')
 def test_original_not_supplied_is_not_checked(self):
  with tempfile.TemporaryDirectory() as root:
   source,pdf,out=self.fixture(root);r=verify(out/'report-manifest.json',source);self.assertFalse(r['originalChecked']);self.assertIsNone(r['originalMatches'])

