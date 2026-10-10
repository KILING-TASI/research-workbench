import unittest,tempfile,json,hashlib
from pathlib import Path
from unittest.mock import patch
from subprocess import CompletedProcess
from fund_report_holdings import independent_ruiyuan
class Tests(unittest.TestCase):
 def fixture(self,root):
  project=root/'project';(project/'cnlookthrough').mkdir(parents=True)
  for name in ['report_cli.py','report_adapter.py','engine.py']:(project/'cnlookthrough'/name).write_text('teaching module','utf-8')
  pdf=root/'source.pdf';pdf.write_bytes(b'local teaching')
  return project,pdf
 def test_explicit_adapter_keeps_dates_identity_and_new_metadata(self):
  with tempfile.TemporaryDirectory() as tmp:
   project,pdf=self.fixture(Path(tmp));expected={'id':'007119','reportDate':'2026-06-30','publishedAt':'2026-08-27','currency':'CNY','sourceSha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'adapterProfile':'ruiyuan-growth-six-column-v1','disclosureScope':'completeEquity','portfolioScope':'fund-all-share-classes','netAssetsCNY':100,'equityMarketValueCNY':50,'inputSchema':'explicit-report-totals-v1','rulesVersion':'six-column-equity-1'}
   def launch(args,**kwargs):
    self.assertEqual(kwargs['cwd'],project.resolve());self.assertNotIn('PYTHONPATH',kwargs['env']);Path(args[-1]).write_text(json.dumps(expected),'utf-8');return CompletedProcess(args,0,'','')
   with patch('subprocess.run',side_effect=launch):result=independent_ruiyuan(pdf,'007119','2026-06-30','2026-08-27','https://example.org/a.pdf','100','50',project)
   self.assertEqual(result['engineSelection']['rulesVersion'],'six-column-equity-1')
 def test_unsupported_profile_and_failure_do_not_silently_fallback(self):
  with tempfile.TemporaryDirectory() as tmp:
   project,pdf=self.fixture(Path(tmp))
   with patch('subprocess.run') as launch:
    with self.assertRaises(ValueError):independent_ruiyuan(pdf,'000001','2026-06-30','2026-08-27','https://example.org/a.pdf','100','50',project)
    launch.assert_not_called()
   with patch('subprocess.run',return_value=CompletedProcess([],2,'','wrong layout')):
    with self.assertRaises(ValueError):independent_ruiyuan(pdf,'007119','2026-06-30','2026-08-27','https://example.org/a.pdf','100','50',project)
if __name__=='__main__':unittest.main()
