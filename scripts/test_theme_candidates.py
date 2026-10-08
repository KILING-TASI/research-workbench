import unittest
from theme_candidates import parse,discover
class Tests(unittest.TestCase):
 def test_string_query_does_not_split_into_characters(self):
  rows=[dict(code='000001',name='红利A',fundType='股票')]
  for terms,exclude in [('红利',None),(['红利'],'A'),(['红利'],[None])]:
   with self.assertRaises(ValueError):discover(rows,terms,exclude)
 def test_catalog_types_preserve_codes(self):
  for raw in ['var r = [[123456,"X","红利A","股票"]];','var r = [["000001","X",null,"股票"]];']:
   with self.assertRaises(ValueError):parse(raw)
 def test_parse(self):self.assertEqual(parse('var r = [["000001","X","红利A","股票型"]];')[0]['code'],'000001')
 def test_no_execution(self):
  with self.assertRaises(ValueError):parse('var r = []; evil();')
 def test_duplicates(self):
  with self.assertRaises(ValueError):parse('var r = [["000001","X","A","股票"],["000001","X","B","股票"]];')
 def test_match_exclude(self):
  rows=[dict(code='000001',name='AI科技A',fundType='股票'),dict(code='000002',name='AI科技C',fundType='股票')]
  r=discover(rows,['AI','科技'],['C'],mode='all');self.assertEqual(r['codes'],['000001']);self.assertIn('未核验',r['candidates'][0]['themeVerification'])
 def test_truncation(self):self.assertTrue(discover([dict(code=str(i),name='红利',fundType='股票') for i in range(3)],['红利'],limit=1)['truncated'])
if __name__=='__main__':unittest.main()
