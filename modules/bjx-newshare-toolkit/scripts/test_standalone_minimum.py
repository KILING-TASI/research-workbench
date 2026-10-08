import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class MinimalStandalone(unittest.TestCase):
    def test_threshold_without_project_modules_or_site_packages(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in ['standalone.py','public_issuance_data.py']:
                shutil.copy2(Path(__file__).parent/name,root/name)
            output=root/'result.json'
            run=subprocess.run([sys.executable,'-S',str(root/'standalone.py'),'--out',str(output),'threshold','--price','10','--rate-pct','1','--max-shares','100000'],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr)
            result=json.loads(output.read_text('utf-8'))
            self.assertEqual(result['shares'],10000);self.assertEqual(result['funds'],'100000');self.assertTrue(result['reachable'])
