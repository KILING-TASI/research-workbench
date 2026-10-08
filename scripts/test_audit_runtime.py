import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import audit_workbench as module


class RuntimeTests(unittest.TestCase):
    def test_bad_path_preserves_later_check(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'references').mkdir()
            (root / 'data.json').write_text('[]')
            (root / 'good.py').write_text('pass')
            registry = {'capabilities': [{'dataPath': 'data.json', 'recordsKey': '', 'entrypoints': ['../outside.py', 'good.py'], 'checks': ['../outside.py', 'good.py']}]}
            (root / 'references/capabilities.json').write_text(json.dumps(registry))
            with patch.object(module, 'ROOT', root), patch.object(module.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')) as run:
                result = module.audit(root, True)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(result['testSummary']['failed'], 1)
            self.assertEqual(result['testSummary']['passed'], 1)
            self.assertFalse(result['capabilities'][0]['entrypointStatus']['../outside.py'])

    def test_atomic_save_archives_prior_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = module.save(root, {'version': 1})
            original = path.read_bytes()
            module.save(root, {'version': 2})
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')), {'version': 2})
            archive = root / 'outputs/bjx-newshare-toolkit/research/audit-history'
            self.assertEqual(list(archive.glob('*.json'))[0].read_bytes(), original)
            self.assertEqual(list(path.parent.glob('.audit-*.tmp')), [])

    def run_audit(self, node=None, available=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'references').mkdir()
            (root / 'check.mjs').write_text('console.log("ok")', encoding='utf-8')
            (root / 'data.json').write_text('[]', encoding='utf-8')
            registry = {'capabilities': [{'dataPath': 'data.json', 'recordsKey': '',
                         'entrypoints': ['check.mjs'], 'checks': ['check.mjs']}]}
            (root / 'references/capabilities.json').write_text(json.dumps(registry))
            with patch.object(module, 'ROOT', root), patch.object(module.shutil, 'which', return_value=available), patch.object(module.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'ok', '')) as run:
                result = module.audit(root, True, node)
                command = run.call_args.args[0] if run.called else None
                return result, command

    def test_mjs_uses_path_node(self):
        result, command = self.run_audit(available='/usr/bin/node')
        self.assertEqual(command[0], '/usr/bin/node')
        self.assertEqual(result['testSummary']['passed'], 1)

    def test_explicit_runtime_wins(self):
        result, command = self.run_audit(node='custom-node', available='other-node')
        self.assertEqual(command[0], 'custom-node')

    def test_missing_runtime_does_not_execute_python(self):
        result, command = self.run_audit()
        self.assertIsNone(command)
        self.assertEqual(result['testSummary']['failed'], 1)
        self.assertEqual(len(result['capabilities'][0]['checksResult']), 1)


if __name__ == '__main__':
    unittest.main()
