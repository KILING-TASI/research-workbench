import json,unittest
from publish_bjx_delivery import distribution_bytes
class DistributionTests(unittest.TestCase):
 def test_market_records_and_predictions_not_redistributed(self):
  raw=json.dumps({'records':[{'code':'920196','price':14.21}],'predictionArchive':[{'private':'research'}]}).encode()
  result=json.loads(distribution_bytes('assets/data.json',raw))
  self.assertEqual(result['records'],[]);self.assertEqual(result['predictionArchive'],[])
  self.assertNotIn(b'920196',distribution_bytes('assets/data.json',raw))
 def test_evidence_caches_cleared_preserving_container_type(self):
  for rel in ['assets/calendar-verified-fields.json','assets/calendar-pe-evidence.json']:
   self.assertEqual(json.loads(distribution_bytes(rel,b'{"records":{"sample":1}}')), {})
   self.assertEqual(json.loads(distribution_bytes(rel,b'[{"sample":1}]')), [])
 def test_preview_replaced_and_code_unmodified(self):
  self.assertNotIn(b'920196',distribution_bytes('assets/bjx-panel.html',b'<p>920196</p>'))
  self.assertEqual(distribution_bytes('scripts/model.py',b'code'),b'code')
