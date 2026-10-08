import subprocess,sys,unittest
from pathlib import Path

class Tests(unittest.TestCase):
    def test_bjx_import_survives_loaded_main_evidence_module(self):
        root=Path(__file__).resolve().parents[1]
        code='''import sys
from pathlib import Path
root=Path(sys.argv[1])
sys.path.insert(0,str(root/'scripts'))
import research_evidence
main_path=research_evidence.__file__
sys.path.insert(0,str(root/'modules/bjx-newshare-toolkit/scripts'))
import issuance_research,bjx_research_evidence
assert issuance_research.export is bjx_research_evidence.export
assert research_evidence.__file__==main_path
assert callable(bjx_research_evidence.verify)
'''
        p=subprocess.run([sys.executable,'-c',code,str(root)],capture_output=True,text=True,timeout=30)
        self.assertEqual(p.returncode,0,p.stderr)
    def test_legacy_topic_cli_is_preserved(self):
        root=Path(__file__).resolve().parents[1]
        p=subprocess.run([sys.executable,str(root/'modules/bjx-newshare-toolkit/scripts/research_evidence.py'),'--help'],capture_output=True,text=True,timeout=30)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn('export',p.stdout)

if __name__=='__main__':unittest.main()
