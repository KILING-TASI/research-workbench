import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from delivery_preflight import inspect, RESOURCES
from update_delivery_candidate import main


class Preflight(unittest.TestCase):
    def test_empty_install_reports_exact_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            result = inspect(directory, 'update')
            self.assertEqual(result['missingResources'], RESOURCES['update'])
            self.assertFalse(result['networkAttempted'])

    def test_file_not_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / 'assets/data.json').mkdir(parents=True)
            self.assertIn('assets/data.json', inspect(directory, 'historical-cash')['missingResources'])

    def test_presence_does_not_claim_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in RESOURCES['historical-cash']:
                path = Path(directory) / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('{}')
            self.assertEqual(inspect(directory, 'historical-cash')['status'], 'resources-present')

    def test_update_missing_resources_never_attempts_network(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'new'
            with patch('sys.argv', ['update', '--out-dir', str(output)]), patch('update_delivery_candidate.inspect_resources', return_value={'missingResources': ['assets/data.json']}), patch('update_delivery_candidate.subprocess.run') as run:
                with self.assertRaises(SystemExit) as stopped:
                    main()
            self.assertEqual(stopped.exception.code, 2)
            run.assert_not_called()
            result = json.loads((output / 'update-report.json').read_text('utf-8'))
            self.assertEqual(result['status'], 'missing-project-resources')
            self.assertFalse(result['liveFilesOverwritten'])

    def test_unknown_operation_rejected(self):
        with self.assertRaises(ValueError):
            inspect('.', 'unknown')
