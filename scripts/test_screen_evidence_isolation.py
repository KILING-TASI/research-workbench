import unittest
from multidimensional_screen import screen,markdown
class Tests(unittest.TestCase):
 def test_all_metric_sources_preserved_and_invalid_list_unknown(self):
  ev=dict(value=100,unit='CNY',basis='reported',observedAt='2026-10-02',sourceUrl='https://example.org/first',sourceUrls=['https://example.org/first','https://example.org/second'])
  s=dict(asOf='2026-10-03',candidates=[dict(kind='ETF',market='CN',code='510300',fields={'aumCNY':ev})],conditions=[dict(kind='metric',field='aumCNY',op='gt',value=10)])
  text=markdown(screen(s),s);self.assertIn('https://example.org/second',text)
  for bad in ['https://example.org/first',[],['https://example.org/other'],['https://example.org/first','file:///bad']]:
   ev['sourceUrls']=bad;self.assertTrue(screen(s)['unknown'])
 def test_future_evidence_keeps_other_candidate(self):
  def row(code,date):return dict(kind='ETF',market='CN',code=code,fields={'aumCNY':dict(value=100,unit='CNY',basis='reported',observedAt=date,sourceUrl='https://example.org/report')})
  r=screen(dict(asOf='2026-10-03',candidates=[row('510300','2026-10-02'),row('510500','2026-10-04')],conditions=[dict(kind='metric',field='aumCNY',op='gt',value=10)]))
  self.assertEqual([x['code'] for x in r['selected']],['510300']);self.assertEqual([x['code'] for x in r['unknown']],['510500']);self.assertEqual(r['coverage'][0]['usable'],1);self.assertEqual(r['coverage'][0]['total'],2)
 def test_rank_source_and_market_in_report(self):
  s=dict(asOf='2026-10-03',candidates=[dict(kind='ETF',market='HK',code='02800',tags={'theme':dict(value=['宽基'],observedAt='2026-10-02',basis='contract',sourceUrl='https://example.org/contract')},fields={'aumCNY':dict(value=100,unit='CNY',basis='reported',observedAt='2026-10-02',sourceUrl='https://example.org/rank')})],conditions=[dict(kind='tag',dimension='theme',value='宽基')],rank=dict(field='aumCNY',direction='desc'))
  text=markdown(screen(s),s);self.assertIn('ETF | HK | 02800',text);self.assertIn('[排序数据来源](https://example.org/rank)',text);self.assertIn('口径：reported',text)
 def test_invalid_rule_still_rejected(self):
  with self.assertRaises(ValueError):screen(dict(asOf='2026-10-03',candidates=[dict(kind='ETF',market='CN',code='510300')],conditions=[dict(kind='metric',field='fake',op='gt',value=1)]))
if __name__=='__main__':unittest.main()
