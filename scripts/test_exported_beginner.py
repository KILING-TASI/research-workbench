"""Regression: an exported Skill must run its new beginner launcher on its own."""
import subprocess,sys,tempfile,unittest,zipfile
from pathlib import Path
from build_package import build

class ExportedBeginner(unittest.TestCase):
    def test_exported_source_runs_without_other_repositories_or_site_packages(self):
        source=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);archive=root/'skill.zip';build(source,archive)
            with zipfile.ZipFile(archive) as z:z.extractall(root/'source')
            exported=root/'source/research-workbench'
            self.assertTrue((exported/'research_workbench/_entry.py').is_file())
            self.assertTrue((exported/'pyproject.toml').is_file())
            run=subprocess.run([sys.executable,'-I','-S',str(exported/'try_demo.py'),'--no-open','--out-dir',str(root/'demo')],cwd=exported,capture_output=True,timeout=120)
            self.assertEqual(run.returncode,0,run.stderr)
            self.assertTrue(list(root.glob('demo*/*.html')))

if __name__=='__main__':unittest.main()
