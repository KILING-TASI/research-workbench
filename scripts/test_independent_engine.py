import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from subprocess import CompletedProcess,TimeoutExpired
from independent_engine import run

class Tests(unittest.TestCase):
    def test_bundle_discovery_replay_and_input_tamper(self):
        import json
        from independent_engine import bundle
        from research_results import publish
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);project,source,out=self.fixture(root)
            source.write_text(json.dumps({'asOf':'2026-09-30','positions':[{'id':'均衡基金组合'}]}),'utf-8')
            def fake(args,**kwargs):
                output=Path(args[-1]);output.write_text('{}' if args[-3]=='json' else '# 教学报告\n\n已知部分与未知部分分开。','utf-8')
                return CompletedProcess(args,0,'','')
            with patch('independent_engine.subprocess.run',side_effect=fake):
                bundle('lookthrough',project,root/'first',input_path=source)
                bundle('lookthrough',project,root/'second',continue_from=root/'first')
                found=publish(root,root/'index.md','均衡基金组合');self.assertEqual(len(found),2)
                (root/'first/input.json').write_text('{}','utf-8')
                with self.assertRaisesRegex(ValueError,'改动'):bundle('lookthrough',project,root/'tampered',continue_from=root/'first')
                self.assertFalse((root/'tampered').exists())
    def test_bundle_error_does_not_publish_partial_success(self):
        import json
        from independent_engine import bundle
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);project,source,out=self.fixture(root)
            with patch('independent_engine.subprocess.run',return_value=CompletedProcess([],2,'','bad input')):
                with self.assertRaises(ValueError):bundle('lookthrough',project,root/'failed',input_path=source)
            self.assertFalse((root/'failed').exists())
    def test_schema_mismatch_rejected_before_external_execution(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            project,source,out=self.fixture(Path(tmp));source.write_text(json.dumps({'inputSchema':'cnreconcile-pairs-v1'}),'utf-8')
            with patch('independent_engine.subprocess.run') as execute:
                with self.assertRaisesRegex(ValueError,'schema'):run('lookthrough',project,source,out)
                execute.assert_not_called()
    def test_unverified_owners_not_registered_as_callable(self):
        from independent_engine import contract
        self.assertEqual(contract('lookthrough')['inputSchema'],'cnlookthrough-nodes-v1')
        with self.assertRaises(ValueError):contract('portfolio')

    def fixture(self,root):
        project=root/'project';(project/'cnlookthrough').mkdir(parents=True);(project/'cnlookthrough/__main__.py').write_text('','utf-8')
        source=root/'input.json';source.write_text('{}','utf-8');return project,source,root/'new.md'
    def test_absolute_io_and_explicit_project_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            project,source,out=self.fixture(Path(tmp))
            def fake(args,**kwargs):
                self.assertEqual(kwargs['cwd'],project.resolve());self.assertNotIn('PYTHONPATH',kwargs['env'])
                self.assertEqual(args[-1],str(out));out.write_text('report','utf-8');return CompletedProcess(args,0,'','')
            with patch('independent_engine.subprocess.run',side_effect=fake):r=run('lookthrough',project,source,out)
            self.assertEqual(r['status'],'generated-not-reverified')
    def test_bad_location_and_overwrite_rejected_before_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            project,source,out=self.fixture(Path(tmp));out.write_text('old','utf-8')
            with patch('independent_engine.subprocess.run') as mocked:
                with self.assertRaises(ValueError):run('lookthrough',project,source,out)
                with self.assertRaises(ValueError):run('financial',project,source,Path(tmp)/'other.md')
                mocked.assert_not_called()
    def test_error_timeout_and_missing_output_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            project,source,out=self.fixture(Path(tmp))
            for response in [CompletedProcess([],2,'','invalid input'),CompletedProcess([],0,'','')]:
                with patch('independent_engine.subprocess.run',return_value=response):
                    with self.assertRaises(ValueError):run('lookthrough',project,source,out)
            with patch('independent_engine.subprocess.run',side_effect=TimeoutExpired([],60)):
                with self.assertRaises(ValueError):run('lookthrough',project,source,out)

if __name__=='__main__':unittest.main()
