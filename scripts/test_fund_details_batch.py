import unittest,tempfile
from pathlib import Path
from unittest.mock import patch
from fund_details_batch import run
class Tests(unittest.TestCase):
 def test_report_generation_failure_is_not_saved_as_success(self):
  with tempfile.TemporaryDirectory() as directory:
   out=Path(directory)/'new'
   with patch('fund_details_batch.get',return_value='response'),patch('fund_details_batch.extract',return_value=dict(name='测试',gaps=[])),patch('fund_details_batch.markdown',side_effect=ValueError('说明失败')):r=run(dict(asOf='2026-10-03',requests=[dict(code='000001')]),out)
   self.assertEqual(r['failedCount'],1);self.assertFalse((out/'000001/result.json').exists());self.assertTrue((out/'000001/provider.js').exists())
 def test_failed_item_does_not_stop_next_and_raw_retained(self):
  with tempfile.TemporaryDirectory() as directory:
   with patch('fund_details_batch.get',return_value='original'),patch('fund_details_batch.extract',side_effect=[ValueError('身份不匹配'),dict(name='第二只',gaps=[])]),patch('fund_details_batch.markdown',return_value='说明'):
    r=run(dict(asOf='2026-10-03',requests=[dict(code='000001'),dict(code='000002')]),Path(directory)/'new')
   self.assertEqual(r['availableCount'],1);self.assertEqual(r['failedCount'],1);self.assertTrue(r['rows'][0]['rawRetained'])
 def test_duplicate_rejected_before_network_and_output(self):
  with tempfile.TemporaryDirectory() as directory:
   out=Path(directory)/'new'
   with patch('fund_details_batch.get') as get:
    with self.assertRaises(ValueError):run(dict(asOf='2026-10-03',requests=[dict(code='000001'),dict(code='000001')]),out)
    get.assert_not_called();self.assertFalse(out.exists())
if __name__=='__main__':unittest.main()
