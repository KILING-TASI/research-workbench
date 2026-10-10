import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from announcement_reuse import review


class AnnouncementReuseTests(unittest.TestCase):
    def setUp(self):
        self.record = json.loads((Path(__file__).resolve().parents[1] /
                                  'references/examples/announcement-sidecar-920188.json').read_text('utf-8'))

    def test_digest_mismatch_rejected(self):
        with patch('announcement_reuse.Path.read_bytes', return_value=b'%PDF-tampered'):
            with self.assertRaisesRegex(ValueError, 'digest mismatch'):
                review(self.record, 'unused.pdf')

    def test_version_conflict_before_read(self):
        self.record['source_version']['announcement_number'] = '2026-999'
        with patch('announcement_reuse.Path.read_bytes') as reader:
            with self.assertRaisesRegex(ValueError, 'version conflict'):
                review(self.record, 'unused.pdf')
            reader.assert_not_called()

    def test_unknown_clock_cannot_be_used_prospectively(self):
        before = copy.deepcopy(self.record)
        with self.assertRaisesRegex(ValueError, 'Prospective use unsupported'):
            review(self.record, 'unused.pdf', prospective=True)
        self.assertEqual(self.record, before)
        self.assertIsNone(self.record['times']['historical_available_at']['value'])

    def test_acquisition_time_cannot_replace_publication(self):
        self.record['times']['published_at']['value'] = self.record['times']['retrieved_at']['value']
        with self.assertRaisesRegex(ValueError, 'no certified public availability'):
            review(self.record, 'unused.pdf')


if __name__ == '__main__':
    unittest.main()
