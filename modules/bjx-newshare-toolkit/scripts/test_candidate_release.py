import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from release_workbench_candidate import publish,restore,digest,replace
from compare_delivery_data import compare
from build_bjx_workbench import payload

class Release(unittest.TestCase):
 def setup_pair(self,p):
  a=p/'assets';c=p/'candidate';a.mkdir();c.mkdir()
  old={'records':[{'code':'1','price':10}], 'fetchedAt':'old','source':'test','predictionArchive':[1]}
  new={**old,'records':[{'code':'1','price':11}],'fetchedAt':'new','modelOptimizationRun':False}
  for folder,data in [(a,old),(c,new)]:
   (folder/'data.json').write_text(json.dumps(data));(folder/'bjx-panel.html').write_text('<script id="dataset" type="application/json">'+json.dumps(payload(data,{},{}))+'</script>')
  (a/'calendar-verified-fields.json').write_text('{}')
  diff=compare(old,new,{});diff['inputs']={str(x):digest(x) for x in [a/'data.json',c/'data.json',a/'calendar-verified-fields.json']};(c/'data-diff.json').write_text(json.dumps(diff))
  return a,c,p/'backup',digest(c/'data-diff.json')
 def test_publish_and_restore(self):
  with tempfile.TemporaryDirectory() as t:
   a,c,b,h=self.setup_pair(Path(t));before=digest(a/'data.json');r=publish(c,a,b,h)
   self.assertEqual(r['status'],'published-reviewed-pair');self.assertEqual(digest(a/'data.json'),digest(c/'data.json'))
   restore(b,a);self.assertEqual(digest(a/'data.json'),before)
 def test_second_write_failure_restores_both(self):
  with tempfile.TemporaryDirectory() as t:
   a,c,b,h=self.setup_pair(Path(t));before={n:digest(a/n) for n in ['data.json','bjx-panel.html']}
   def fail(source,target):
    if target.name=='bjx-panel.html':raise OSError('simulated disk failure')
    replace(source,target)
   with patch('release_workbench_candidate.replace',side_effect=fail):
    with self.assertRaises(OSError):publish(c,a,b,h)
   self.assertEqual(before,{n:digest(a/n) for n in before})
 def test_mismatched_page_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   a,c,b,h=self.setup_pair(Path(t));s=(c/'bjx-panel.html').read_text().replace('"price": 11','"price": 99');(c/'bjx-panel.html').write_text(s)
   with self.assertRaises(ValueError):publish(c,a,b,h)
   self.assertFalse(b.exists())
 def test_stale_research_evidence_rejected(self):
  for key,value in [('announcements',[{'title':'stale'}]),('announcementVersionReview',{'status':'wrong'}),('annualRecords',[]),('officialFieldVerification',{'price':{'status':'fake'}})]:
   with tempfile.TemporaryDirectory() as t:
    a,c,b,h=self.setup_pair(Path(t));d=payload(json.loads((c/'data.json').read_text()),{}, {})
    if key=='annualRecords':d[key]=value
    else:d['records'][0][key]=value
    (c/'bjx-panel.html').write_text('<script id="dataset" type="application/json">'+json.dumps(d)+'</script>')
    with self.assertRaises(ValueError):publish(c,a,b,h)
    self.assertFalse(b.exists())
 def test_unreviewed_calendar_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   a,c,b,h=self.setup_pair(Path(t));(a/'bse-trading-calendar-2026.json').write_text('{"year":2026}')
   with self.assertRaisesRegex(ValueError,'Calendar absent'):publish(c,a,b,h)
   self.assertFalse(b.exists())
if __name__=='__main__':unittest.main()
