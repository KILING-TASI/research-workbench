import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from extract_issuance_evidence import extract


class ManifestHash(unittest.TestCase):
    def test_changed_original_is_rejected_before_parsing(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'original.pdf';path.write_bytes(b'%PDF-changed')
            with patch('pypdf.PdfReader') as reader:
                result=extract({'documents':[{'code':'920196','name':'teaching','file':str(path),'kind':'issue','sha256':'0'*64}]})
            reader.assert_not_called()
            self.assertEqual(result['documents'][0]['status'],'failed')
            self.assertIn('hash mismatch',result['documents'][0]['reason'])
