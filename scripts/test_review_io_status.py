import json, subprocess, sys, tempfile, unittest, hashlib
from pathlib import Path
from review_io import publish


class Tests(unittest.TestCase):
    def test_execution_and_evidence_separate_and_receipt_matches(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'new'; publish({'sampleType':'teaching'}, {'conclusion':'<script>bad</script>', 'status':'partial'}, out, '核对')
            result=json.loads((out/'result.json').read_text('utf-8'))
            self.assertEqual(result['status'],'partial'); self.assertEqual(result['executionStatus'],'completed')
            html=(out/'report.html').read_text('utf-8'); self.assertIn('计算已完成，证据仍需复查',html); self.assertNotIn('<script>bad</script>',html)
            receipt=json.loads((out/'receipt.json').read_text('utf-8'))
            for name,sha in receipt['files'].items(): self.assertEqual(hashlib.sha256((out/name).read_bytes()).hexdigest(),sha)
            before=(out/'result.json').read_bytes()
            with self.assertRaises(ValueError): publish({}, {}, out, '覆盖')
            self.assertEqual((out/'result.json').read_bytes(),before)
    def test_cli_phases_failure_and_no_partial_report(self):
        repo=Path(__file__).parents[1]
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'claim'; command=[sys.executable,str(repo/'scripts/claim_evidence_review.py'),'review','--input',str(repo/'references/examples/claim-evidence-teaching.json'),'--out-dir',str(out)]
            p=subprocess.run(command,capture_output=True,encoding='utf-8'); self.assertEqual(p.returncode,0,p.stderr)
            for n in (1,2,3):self.assertIn(f'进度 {n}/3',p.stderr)
            frozen=(out/'result.json').read_bytes(); p=subprocess.run(command,capture_output=True,encoding='utf-8')
            self.assertEqual(p.returncode,2);self.assertIn('旧结果保留',p.stderr);self.assertEqual((out/'result.json').read_bytes(),frozen)
            bad=Path(temp)/'bad.json';bad.write_text('{"inputSchema":"unknown"}','utf-8');command[command.index('--input')+1]=str(bad);command[-1]=str(Path(temp)/'failed')
            p=subprocess.run(command,capture_output=True,encoding='utf-8');self.assertEqual(p.returncode,2);self.assertFalse((Path(temp)/'failed').exists())


if __name__=='__main__': unittest.main()
