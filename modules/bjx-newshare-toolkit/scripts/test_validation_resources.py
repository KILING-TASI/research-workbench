import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from validation_resources import fixture_path


class ValidationResources(unittest.TestCase):
    def test_explicit_directory_has_no_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);assets=root/'assets';assets.mkdir();(assets/'data.json').write_text('{}')
            with patch.dict('os.environ',{'BJX_VALIDATION_DATA_DIR':str(root/'other')}):
                with self.assertRaises(FileNotFoundError):fixture_path(assets,'data.json')

    def test_explicit_file_selected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'data.json';path.write_text('{}')
            with patch.dict('os.environ',{'BJX_VALIDATION_DATA_DIR':str(root)}):
                self.assertEqual(fixture_path(root/'absent','data.json'),path)

    def test_path_traversal_rejected(self):
        with self.assertRaises(ValueError):fixture_path('.', '../data.json')
