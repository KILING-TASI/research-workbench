# SPDX-License-Identifier: MIT
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from evidence_status_review import review
from review_io import publish
ROOT = Path(__file__).resolve().parents[1]

class EvidenceStatusTest(unittest.TestCase):
    def setUp(self):
        self.spec=json.loads((ROOT/'examples/expansion-teaching/evidence-status-teaching.json').read_text(encoding='utf-8'))
    def test_states_and_future(self):
        self.assertEqual([r['reviewStatus'] for r in review(self.spec)['records']], ['available','stale','failed','unauthorized'])
        self.spec['records'][0]['acquiredAt']='2026-10-02T09:00:00+08:00'
        self.assertEqual(review(self.spec)['records'][0]['reviewStatus'],'after-cutoff')
    def test_unknown_window_and_duplicate(self):
        self.spec['maxAgeDays']=True
        with self.assertRaises(ValueError): review(self.spec)
        self.spec['maxAgeDays']=7;self.spec['records'].append(copy.deepcopy(self.spec['records'][0]))
        with self.assertRaises(ValueError): review(self.spec)
    def test_frozen_report_and_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'report';r=review(self.spec);r['conclusion']='<script>alert(1)</script>'
            publish(self.spec,r,out,'教学')
            self.assertNotIn('<script>alert(1)</script>',(out/'report.html').read_text(encoding='utf-8'))
            with self.assertRaises(ValueError):publish(self.spec,r,out,'教学')

if __name__=='__main__':unittest.main()
