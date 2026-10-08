import unittest
from eia_inventory_source import parse,TITLE
class Tests(unittest.TestCase):
 def test_invalid_requested_window_not_silent_empty_data(self):
  for start,end in [('2026-02-01','2026-01-01'),('20260101','2026-01-31'),(None,'2026-01-31')]:
   with self.subTest(start=start),self.assertRaises(ValueError):parse(self.html(),start,end)
 def html(self,pairs=None,title=TITLE):
  pairs=pairs or [('01/02','410,000'),('01/09','411,000'),('','',''),('','',''),('','','')]
  cells="<td class='B6'>2026-Jan</td>"+''.join("<td class='B5'>"+p[0]+"</td><td class='B3'>"+p[1]+"</td>" for p in pairs)
  return ('<title>'+title+'</title><table><tr>'+cells+'</tr></table>').encode()
 def test_exact_weekly_dates_and_no_publication_guess(self):
  points,missing=parse(self.html(),'2026-01-01','2026-01-31');self.assertEqual([p['value'] for p in points],[410000,411000]);self.assertIsNone(points[0]['publishedAt']);self.assertEqual(missing,[])
 def test_wrong_spr_scope_rejected(self):
  with self.assertRaisesRegex(ValueError,'SPR'):parse(self.html(title=TITLE.replace('excluding','including')),'2026-01-01','2026-01-31')
 def test_missing_value_not_zero(self):
  points,missing=parse(self.html([('01/02','410,000'),('01/09','.'),('',''),('',''),('','')]),'2026-01-01','2026-01-31');self.assertEqual(len(points),1);self.assertEqual(missing,['2026-01-09'])
 def test_unpaired_and_wrong_month_rejected(self):
  for pairs in [[('','410,000')]+[('','')]*4,[('02/01','410,000')]+[('','')]*4]:
   with self.assertRaises(ValueError):parse(self.html(pairs),'2026-01-01','2026-03-01')
 def test_duplicate_period_rejected(self):
  with self.assertRaisesRegex(ValueError,'重复'):parse(self.html([('01/02','410,000'),('01/02','411,000')]+[('','')]*3),'2026-01-01','2026-01-31')
if __name__=='__main__':unittest.main()
