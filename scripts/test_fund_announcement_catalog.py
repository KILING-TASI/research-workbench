import unittest
from unittest.mock import patch
import market_collect as m
class FundAnnouncementCatalog(unittest.TestCase):
 def item(self,code='159869',date='2026-09-01',ident='a'):
  return dict(FUNDCODE=code,PUBLISHDATE=date,TITLE='基金公告',ID=ident)
 def test_dates_are_filtered_no_attachment_guessed(self):
  with patch.object(m,'fetch',return_value={'Data':[self.item(date='2026-10-01',ident='future'),self.item(),self.item(date='2025-01-01',ident='b')]}):rows,urls=m.fund_announcements('159869','2026-01-01','2026-09-30')
  self.assertEqual(len(rows),1);self.assertIsNone(rows[0]['url']);self.assertFalse(rows[0]['originalVerified']);self.assertIn('JJGG',urls[0])
 def test_wrong_code_is_rejected(self):
  with patch.object(m,'fetch',return_value={'Data':[self.item(code='159870')]}):
   with self.assertRaisesRegex(ValueError,'代码'):m.fund_announcements('159869','2026-01-01','2026-09-30')
 def test_duplicate_is_rejected(self):
  with patch.object(m,'fetch',return_value={'Data':[self.item(),self.item()]}):
   with self.assertRaisesRegex(ValueError,'重复'):m.fund_announcements('159869','2026-01-01','2026-09-30')
 def test_empty_is_not_no_announcements(self):
  with patch.object(m,'fetch',return_value={'Data':[]}):
   with self.assertRaisesRegex(ValueError,'覆盖未确认'):m.fund_announcements('159869','2026-01-01','2026-09-30')
 def test_unsorted_blocks_early_stop(self):
  with patch.object(m,'fetch',return_value={'Data':[self.item(date='2025-01-01'),self.item(ident='b')]}):
   with self.assertRaisesRegex(ValueError,'顺序'):m.fund_announcements('159869','2026-01-01','2026-09-30')
