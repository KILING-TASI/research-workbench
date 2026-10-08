import unittest
from fund_details import markdown,attach_manager_report,attach_holdings_report
from unittest.mock import patch
class Tests(unittest.TestCase):
 def test_channel_name_is_clue_not_current_tenure(self):
  r=dict(name='测试基金',code='000001',asOf='2026-10-03',facts=dict(managerClues=dict(value=[dict(name='测试经理')],sourceUrl='https://example.org',retrievedAt=None)),stagePerformance=[],gaps=[],limitations=[],sourceUrl='https://example.org',riskNotice='')
  text=markdown(r);self.assertIn('测试经理',text);self.assertIn('不是已核验',text);self.assertIn('多个姓名不自动表示共同管理',text);self.assertIn('归档未提供',text);self.assertIn('不能用本条网页线索替代',text)
 def test_report_identity_and_cutoff_before_pdf_read(self):
  for archive in [dict(code='000002',reportDate='2025-12-31',metadata=dict(publishedAt='2026-03-31')),dict(code='000001',reportDate='2025-12-31',metadata=dict(publishedAt='2026-10-04'))]:
   with patch('report_manager_tenure.extract_archive') as extract:
    with self.assertRaises(ValueError):attach_manager_report(dict(code='000001',asOf='2026-10-03',facts={}),archive)
    extract.assert_not_called()
 def test_report_extraction_failure_not_silently_ignored(self):
  archive=dict(code='000001',reportDate='2025-12-31',metadata=dict(publishedAt='2026-03-31'))
  r=dict(code='000001',asOf='2026-10-03',facts={})
  with patch('report_manager_tenure.extract_archive',side_effect=ValueError('PDF哈希不一致')):
   with self.assertRaisesRegex(ValueError,'哈希'):attach_manager_report(r,archive)
  self.assertNotIn('managerReportEvidence',r['facts'])
 def test_different_date_name_sets_not_verified_role_conflict(self):
  r=dict(code='000001',asOf='2026-10-03',facts=dict(managerClues=dict(value=[dict(name='渠道姓名')])) )
  archive=dict(code='000001',reportDate='2025-12-31',metadata=dict(publishedAt='2026-03-31'))
  with patch('report_manager_tenure.extract_archive',return_value=dict(managers=[dict(name='报告姓名')])):
   attach_manager_report(r,archive)
  comparison=r['facts']['managerReportEvidence']['channelNameComparison']
  self.assertEqual(comparison['channelOnly'],['渠道姓名']);self.assertEqual(comparison['reportOnly'],['报告姓名']);self.assertFalse(comparison['currentRoleConflictVerified'])
 def test_holdings_changed_pdf_rejected_before_candidate(self):
  import tempfile
  from pathlib import Path
  with tempfile.TemporaryDirectory() as directory:
   pdf=Path(directory)/'original.pdf';pdf.write_bytes(b'changed')
   with patch('report_screen_bridge.candidate') as candidate:
    with self.assertRaisesRegex(ValueError,'哈希'):
     attach_holdings_report(dict(code='000001',asOf='2026-10-03',facts={}),dict(code='000001',documentPath=str(pdf),sha256='0'*64))
    candidate.assert_not_called()
 def test_holdings_other_fund_rejected(self):
  with self.assertRaisesRegex(ValueError,'代码'):
   attach_holdings_report(dict(code='000001',facts={}),dict(code='000002'))
 def test_verified_snapshot_replaces_stale_gap_without_current_claim(self):
  import tempfile,hashlib
  from pathlib import Path
  with tempfile.TemporaryDirectory() as directory:
   pdf=Path(directory)/'original.pdf';pdf.write_bytes(b'original')
   r=dict(code='000001',asOf='2026-10-03',facts={},gaps=['持仓股票/债券仅代码线索，缺报告日权重及合计核对','规模金额单位与报告原文尚未核实'])
   archive=dict(code='000001',documentPath=str(pdf),sha256=hashlib.sha256(pdf.read_bytes()).hexdigest())
   with patch('report_screen_bridge.candidate',return_value=dict(holdings={},fields=dict(aumCNY=dict(value=100)))):
    attach_holdings_report(r,archive)
   self.assertIn('当前股票持仓',r['gaps'][0]);self.assertIn('当前规模仍未独立核验',r['gaps'][1]);self.assertEqual(r['facts']['reportNetAssets']['value'],100)
if __name__=='__main__':unittest.main()
