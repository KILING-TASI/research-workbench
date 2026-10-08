import unittest, tempfile,hashlib
from pathlib import Path
from release_clock_review import label_status,inspect
class ClockTests(unittest.TestCase):
    def test_noncanonical_local_times_rejected(self):
        for stamp in ['2026/9/09 09:30','2026/09/09 9:30',True,None]:
            with self.subTest(stamp=stamp),self.assertRaises(ValueError):label_status(stamp,'2026/09/09 10:00')
    def test_duplicate_meta_attributes_rejected(self):
        from release_clock_review import PubDates
        parser=PubDates()
        with self.assertRaises(ValueError):parser.feed('<meta name="PubDate" content="2026/09/09 09:30" content="2026/09/09 09:40">')
    def test_bad_input_structure_rejected(self):
        for spec in [None,dict(clockBasis='same-site-marked-local-time',siteLocalCutoff='2026/09/09 10:00',sources=[None])]:
            with self.assertRaises(ValueError):inspect(spec,Path('.'))
    def test_later_excluded(self):
        self.assertEqual(label_status('2026/09/15 15:34','2026/09/09 10:00'),'marked-after-cutoff-exclude')
    def test_before_is_not_certified_available(self):
        self.assertIn('availability-unproven',label_status('2026/09/09 09:30','2026/09/09 10:00'))
    def test_hidden_metadata_or_duplicate_rejected(self):
        for html in ['<meta name="PubDate" content="2026/09/09 09:30"><p>无日期</p>','<meta name="PubDate" content="2026/09/09 09:30"><meta name="PubDate" content="2026/09/09 09:30"><p>2026/09/09 09:30</p>']:
            with tempfile.TemporaryDirectory() as d:
                p=Path(d)/'source.html';p.write_text(html,encoding='utf-8');spec=dict(clockBasis='same-site-marked-local-time',siteLocalCutoff='2026/09/09 10:00',sources=[dict(id='a',siteId='s',path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())])
                with self.assertRaises(ValueError):inspect(spec,Path(d))
    def test_cross_site_unknown_timezone_rejected(self):
        spec=dict(clockBasis='same-site-marked-local-time',siteLocalCutoff='2026/09/09 10:00',sources=[dict(id='a',siteId='s'),dict(id='b',siteId='t')])
        with self.assertRaises(ValueError):inspect(spec,Path('.'))

class DatePrecisionTests(unittest.TestCase):
    def test_real_style_date_label_does_not_invent_time(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'s.html';p.write_text('<meta name="PubDate" content="2026-07-22 16:18:11"><p>发布时间：2026-07-22</p>',encoding='utf8')
            spec=dict(clockBasis='same-site-marked-local-date',siteLocalCutoffDate='2026-07-22',metadataFormat='%Y-%m-%d %H:%M:%S',sources=[dict(id='a',siteId='s',path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())])
            row=inspect(spec,Path(d))['rows'][0];self.assertEqual(row['status'],'same-date-clock-unknown');self.assertFalse(row['exactClockVerified'])
            spec['siteLocalCutoffDate']='2026-07-21';self.assertEqual(inspect(spec,Path(d))['rows'][0]['status'],'marked-date-after-cutoff-exclude')
            spec['siteLocalCutoffDate']='2026-07-23';self.assertIn('availability-unproven',inspect(spec,Path(d))['rows'][0]['status'])
    def test_unlabelled_date_not_publication_confirmation(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'s.html';p.write_text('<meta name="PubDate" content="2026-07-22"><p>研究提及2026-07-22</p>',encoding='utf8')
            spec=dict(clockBasis='same-site-marked-local-date',siteLocalCutoffDate='2026-07-23',metadataFormat='%Y-%m-%d',sources=[dict(id='a',siteId='s',path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())])
            with self.assertRaises(ValueError):inspect(spec,Path(d))

if __name__=='__main__':unittest.main()
