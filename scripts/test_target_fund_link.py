import unittest,tempfile,hashlib
from pathlib import Path
from target_fund_link import select_records,attach_child
class Tests(unittest.TestCase):
 def row(self,*cells):return dict(cells=list(cells),page=5,tableBBox=[1,2,3,4])
 def test_child_hash_and_period(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'report.pdf';p.write_bytes(b'%PDF-fixture')
   link=dict(target=dict(code='159941',name='目标ETF'),reportDate='2025-12-31',asOf='2026-10-03',publishedAt='2026-03-31',limitations=[])
   child=dict(code='159941',asOf='2026-10-03',reportDate='2025-12-31',status='副本身份及股票持仓勾稽完成',identityStatus='matched',holdings=dict(holdings=[1]),metadata=dict(title='目标ETF2025年度报告',publishedAt='2026-03-31',sourceUrl='https://example.org/report'),documentPath=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
   child['holdings'].update(id=child['code'],reportDate=child['reportDate'],publishedAt=child['metadata']['publishedAt'],sourceUrl=child['metadata']['sourceUrl'],sourceSha256=child['sha256'])
   self.assertEqual(attach_child(link,child)['childReport']['holdingsCount'],1)
   child['holdings']['id']='159915'
   with self.assertRaisesRegex(ValueError,'持仓身份'):attach_child(link,child)
   child['holdings']['id']='159941'
   child['metadata']['publishedAt']='2026-10-04'
   with self.assertRaises(ValueError):attach_child(link,child)
   child['metadata']['publishedAt']='2026-03-31';child['asOf']='2026-09-30'
   with self.assertRaises(ValueError):attach_child(link,child)
   child['asOf']='2026-10-03';child['reportDate']='2025-06-30'
   with self.assertRaises(ValueError):attach_child(link,child)
   child['reportDate']='2025-12-31';p.write_bytes(b'changed')
   with self.assertRaises(ValueError):attach_child(link,child)
 def test_exact_disclosed_code(self):
  r=select_records([self.row('基金名称','目标ETF'),self.row('基金主代码','159941')]);self.assertEqual(r['code'],'159941');self.assertEqual(r['fields']['code'][0]['page'],5)
 def test_name_only_not_guess(self):
  with self.assertRaises(ValueError):select_records([self.row('基金名称','纳指ETF')])
 def test_conflicting_codes(self):
  with self.assertRaises(ValueError):select_records([self.row('基金名称','目标ETF'),self.row('基金主代码','159941'),self.row('基金主代码','159915')])
 def test_conflicting_names(self):
  with self.assertRaises(ValueError):select_records([self.row('基金名称','目标ETF'),self.row('基金名称','另一个ETF'),self.row('基金主代码','159941')])
 def test_parent_four_column_table_not_target(self):
  with self.assertRaises(ValueError):select_records([self.row('基金名称','父基金',None,None),self.row('基金主代码','270042',None,None)])
if __name__=='__main__':unittest.main()
