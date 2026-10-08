import unittest
from verify_original import dates_in
class Tests(unittest.TestCase):
 def test_source_credentials_rejected_before_pdf_read(self):
  from verify_original import verify
  from unittest.mock import patch
  spec=dict(documentPath='not-read.pdf',sourceUrl='https://user:password@example.org/report.pdf',trustedPublisherHosts=['example.org'],sha256='hash',title='报告',issuer='公司',reportDate='2026-06-30',publishedAt='2026-08-31',asOf='2026-10-06',publicationExcerpt='2026年8月31日',fields=[{}])
  with patch('verify_original.Path.read_bytes') as read:
   with self.assertRaisesRegex(ValueError,'无凭据'):verify(spec)
   read.assert_not_called()
 def test_compact_iso_date_not_accepted(self):
  from verify_original import date
  with self.assertRaises(ValueError):date('20260831')
 def test_invalid_merged_column_is_not_a_date(self):
  self.assertEqual(dates_in('2025年66月30日 2026年6月30日'),['2026-06-30'])
 def test_only_invalid_candidates_do_not_match_identity(self):
  self.assertEqual(dates_in('2026年2月30日'),[])
 def test_chinese_and_numeric_dates(self):
  self.assertEqual(dates_in('二〇二六年六月三十日 2026年8月29日'),['2026-06-30','2026-08-29'])
