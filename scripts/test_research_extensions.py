import copy,unittest
from research_extensions import fof

class Tests(unittest.TestCase):
 def spec(self):
  node=lambda holdings:dict(currency='CNY',sourceUrl='https://example.org/report',reportDate='2026-06-30',publishedAt='2026-08-31',holdings=holdings)
  return dict(asOf='2026-10-06',currency='CNY',root='root',nodes={'root':node([dict(kind='fund',node='a',weight=.5),dict(kind='fund',node='b',weight=.5)]),'a':node([dict(kind='stock',id='same',weight=1)]),'b':node([dict(kind='stock',id='same',weight=1)])})
 def test_same_asset_across_funds_adds_once_by_identity(self):
  r=fof(self.spec());self.assertEqual(r['leaves'],{'same':1});self.assertEqual(len(r['paths']),2)
 def test_cross_asset_identity_conflict_rejected(self):
  s=self.spec();s['nodes']['b']['holdings'][0]['kind']='bond'
  with self.assertRaisesRegex(ValueError,'类型冲突'):fof(s)
 def test_source_and_date_invalid_rejected(self):
  for key,value in [('sourceUrl','https://user:secret@example.org/r'),('publishedAt','20260831')]:
   s=self.spec();s['nodes']['a'][key]=value
   with self.assertRaises(ValueError):fof(s)
 def test_missing_child_keeps_unknown_weight(self):
  s=self.spec();del s['nodes']['b'];r=fof(s);self.assertEqual(r['leaves']['same'],.5);self.assertAlmostEqual(sum(x['weight'] for x in r['unknown']),.5)

if __name__=='__main__':unittest.main()
