import json
from pathlib import Path
import tempfile
import unittest
from bounded_engine_gateway import run, reject_bjx_extensions


class TestBoundedGateway(unittest.TestCase):
    def test_unknown_costs_not_silently_dropped(self):
        for extra in ({'financing_rate': 0.1}, {'annual_issues': 20}):
            with self.assertRaises(ValueError):
                reject_bjx_extensions({'operation': 'scenario.v1', 'input': extra})
        with self.assertRaises(ValueError):
            reject_bjx_extensions({'operation': 'scenario.v1', 'input': {'fees': {'slippage_rate': 0.01}}})
        with self.assertRaises(ValueError):
            reject_bjx_extensions({'operation': 'scenario.v1', 'input': {'scenarios': [{'probability': 1}]}})

    def test_native_failed_response_stays_failed_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'engine';root.mkdir()
            (root / 'api.py').write_text("import json,sys\njson.load(sys.stdin)\nprint(json.dumps({'status':'failed','error':{'message':'teaching failure'}}))\nsys.exit(2)\n", encoding='utf-8')
            source = Path(tmp) / 'input.json';source.write_text('{"api_version":"9","operation":"unknown","input":{}}', encoding='utf-8')
            destination = Path(tmp) / 'out'
            result = run('bjx', root, source, destination)
            self.assertEqual(result['status'], 'blocked')
            self.assertEqual(result['engine_response']['status'], 'failed')
            self.assertEqual(result['nativeReturnCode'], 2)
            self.assertEqual((destination / 'input.json').read_bytes(), source.read_bytes())
            with self.assertRaises(ValueError):run('bjx', root, source, destination)

    def test_data_catalog_changes_in_call_refuse_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'engine';root.mkdir();(root / 'rules').mkdir()
            (root / 'rules/version-catalog.json').write_text('{}', encoding='utf-8')
            (root / 'api.py').write_text("from pathlib import Path\nPath('rules/version-catalog.json').write_text('{\"changed\":true}')\nprint('{}')\n", encoding='utf-8')
            source = Path(tmp) / 'input.json';source.write_text('{"operation":"unknown","input":{}}', encoding='utf-8')
            out = Path(tmp) / 'out'
            with self.assertRaises(ValueError):run('bjx', root, source, out)
            self.assertFalse(out.exists())
