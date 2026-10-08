import unittest,tempfile,json,datetime as dt
from pathlib import Path
from unittest.mock import patch
from event_price_review import event_clock,run
class Tests(unittest.TestCase):
 def test_future_disclosure_rejected(self):
  with self.assertRaisesRegex(ValueError,'截止日'):event_clock(dict(eventDate='2026-01-05',publicationDate='2026-02-01'),dt.date(2026,1,15))
 def test_offset_market_date_and_conflict(self):
  s=dict(eventDate='2026-01-05',publishedAt='2026-01-06T01:00:00+00:00',marketTimezone='America/New_York')
  self.assertEqual(event_clock(s,dt.date(2026,1,15))['publicationDate'],'2026-01-05')
  s['publicationDate']='2026-01-06'
  with self.assertRaisesRegex(ValueError,'冲突'):event_clock(s,dt.date(2026,1,15))
 def test_naive_timestamp_rejected(self):
  with self.assertRaisesRegex(ValueError,'偏移'):event_clock(dict(eventDate='2026-01-05',publishedAt='2026-01-05T14:00:00',marketTimezone='America/New_York'),dt.date(2026,1,15))
 @patch('event_price_review.build',return_value=dict(sourceBindings=[]))
 def test_later_disclosure_does_not_use_earlier_event(self,verify):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);points=[dict(date=(dt.date(2026,1,1)+dt.timedelta(days=i)).isoformat(),value=100+i) for i in range(25)];a=p/'archive.json';a.write_text(json.dumps(dict(start='2026-01-01',asOf='2026-01-25',series=[dict(id=k,role='asset',points=points) for k in ['A','B']])))
   s=dict(archive=str(a),assetId='A',comparisonId='B',eventDate='2026-01-05',publicationDate='2026-01-10',publishedAt='2026-01-10T14:00:00-05:00',marketTimezone='America/New_York',eventSourceUrl='https://example.org/event')
   r=run(s,p/'out');self.assertEqual(r['anchorDate'],'2026-01-11');self.assertEqual(r['windows'][0]['before']['end'],'2026-01-09');self.assertEqual(r['windows'][0]['after']['start'],'2026-01-11')
if __name__=='__main__':unittest.main()
