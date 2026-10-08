import unittest,tempfile,json,datetime as dt
from pathlib import Path
from unittest.mock import patch
from event_price_review import run
class Tests(unittest.TestCase):
 def test_invalid_request_fails_before_source_output(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'out'
   for spec in [None,[],{},dict(archive='file',assetId='A',comparisonId='B',eventDate='2026-01-01',eventSourceUrl='https://user:password@example.org')]:
    with self.assertRaises(ValueError):run(spec,out)
    self.assertFalse(out.exists())
 @patch('event_price_review.build')
 def test_window_arithmetic_and_partial_history(self,verify):
  verify.return_value=dict(sourceBindings=[])
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);points=[dict(date=(dt.date(2026,1,1)+dt.timedelta(days=i)).isoformat(),value=100+i) for i in range(15)]
   a=p/'archive.json';a.write_text(json.dumps(dict(start='2026-01-01',asOf='2026-01-15',series=[dict(id=i,role='asset',points=points) for i in ['A','B']])))
   r=run(dict(archive=str(a),assetId='A',comparisonId='B',eventDate='2026-01-08',eventSourceUrl='https://example.org/event'),p/'out')
   self.assertEqual(r['windows'][0]['status'],'both-sides-available');self.assertEqual(r['windows'][0]['before']['end'],'2026-01-07');self.assertLess(r['windows'][0]['before']['end'],r['eventDate']);self.assertEqual(r['windows'][0]['after']['start'],'2026-01-08');self.assertEqual(r['windows'][0]['after']['returnDifference'],0);self.assertEqual(r['windows'][1]['status'],'insufficient-common-history');self.assertEqual(r['eventIdentityStatus'],'input-declared-not-original-verified')

class WindowCalendarTests(unittest.TestCase):
 def test_sparse_dates_not_daily_window(self):
  from event_price_review import window_calendar
  r=window_calendar(['2026-01-01','2026-02-01','2026-03-01'])
  self.assertEqual(r['maximumCalendarGapDays'],31);self.assertEqual(r['continuityStatus'],'sparse-observations-not-daily-window')
 def test_weekend_gap_does_not_claim_calendar_verified(self):
  from event_price_review import window_calendar
  r=window_calendar(['2026-01-02','2026-01-05'])
  self.assertEqual(r['maximumCalendarGapDays'],3);self.assertIn('not-verified',r['continuityStatus'])

if __name__=='__main__':unittest.main()
