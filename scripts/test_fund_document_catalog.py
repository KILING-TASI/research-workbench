import unittest
from fund_document_catalog import select,amendment_clues
class Tests(unittest.TestCase):
 def test_duplicate_id_deduplicates_identical_and_blocks_conflict(self):
  row=dict(FUNDCODE='005827',TITLE='基金合同',PUBLISHDATE='2026-01-01',ID='one')
  self.assertEqual(len(select([row,row],'005827','2026-10-03','contract')),1)
  with self.assertRaisesRegex(ValueError,'冲突'):select([row,{**row,'TITLE':'新版基金合同'}],'005827','2026-10-03','contract')
 def test_full_document_not_summary_or_notice(self):
  items=[dict(FUNDCODE='005827',TITLE=t,PUBLISHDATE=d,ID=str(n)) for n,(t,d) in enumerate([('基金合同','2026-01-01'),('基金合同修订公告','2026-02-01'),('招募说明书摘要','2026-02-01'),('招募说明书','2027-01-01')])]
  self.assertEqual(len(select(items,'005827','2026-10-03','contract')),1);self.assertFalse(select(items,'005827','2026-10-03','prospectus'))
 def test_revision_not_effective_date(self):
  rows=[dict(FUNDCODE='005827',TITLE=t,PUBLISHDATE=d,ID=str(n)) for n,(t,d) in enumerate([('基金合同修订公告','2023-07-08'),('调低旗下基金费率并修订基金合同的公告','2023-08-01'),('调整申购费率公告','2027-01-01'),('基金分红公告','2023-09-01')])]
  r=amendment_clues(rows,'005827','2026-10-03','2023-07-08');self.assertEqual(len(r),2);self.assertIsNone(r[0]['effectiveDate']);self.assertFalse(r[0]['relationVerified']);self.assertEqual(len(r[0]['clueTypes']),2)
 def test_comparison_and_supplement_are_not_full_contracts(self):
  rows=[dict(FUNDCODE='007119',TITLE=t,PUBLISHDATE='2026-01-01',ID=str(i)) for i,t in enumerate(['基金合同更新','基金合同对照表','基金合同补充协议','基金合同修订说明'])]
  self.assertEqual([x['id'] for x in select(rows,'007119','2026-10-08','contract')],['0'])
 def test_auxiliary_material_remains_a_revision_clue(self):
  row=dict(FUNDCODE='007119',TITLE='基金合同对照表',PUBLISHDATE='2026-01-01',ID='comparison')
  clues=amendment_clues([row],'007119','2026-10-08','2026-01-01')
  self.assertEqual(clues[0]['clueTypes'],['法律条款辅助材料']);self.assertFalse(clues[0]['relationVerified']);self.assertIsNone(clues[0]['effectiveDate'])
 def test_other_code_rejected(self):
  with self.assertRaises(ValueError):select([dict(FUNDCODE='000001')],'005827','2026-10-03','contract')
class PaginationTests(unittest.TestCase):
 def payload(self,count,total,page=1):
  return dict(Data=[dict(FUNDCODE='007119',TITLE='基金合同',PUBLISHDATE='2026-01-01',ID=str((page-1)*100+i)) for i in range(count)],TotalCount=total,PageIndex=page,PageSize=100,ErrCode=0)
 def run_payloads(self,payloads):
  import tempfile,json
  from pathlib import Path
  from fund_document_catalog import run
  with tempfile.TemporaryDirectory() as d:
   iterator=iter(payloads)
   return run('007119','2026-10-08','contract',Path(d)/'out',fetch=lambda url:json.dumps(next(iterator)).encode())
 def test_complete_count_requires_all_pages(self):
  r=self.run_payloads([self.payload(100,101),self.payload(1,101,2)])
  self.assertEqual(r['observedItems'],101);self.assertFalse(r['truncated']);self.assertEqual(r['catalogCoverage'],'provider-declared-count-matched')
 def test_short_page_or_wrong_metadata_not_complete(self):
  for payload in [self.payload(1,101),dict(self.payload(1,1),TotalCount=True),dict(self.payload(1,1),PageIndex=2),dict(self.payload(1,1),PageSize=99),dict(self.payload(1,1),ErrCode=1)]:
   with self.assertRaises(ValueError):self.run_payloads([payload])
 def test_total_changes_and_repeated_page_block_completion(self):
  with self.assertRaises(ValueError):self.run_payloads([self.payload(100,101),self.payload(1,102,2)])
  second=self.payload(1,101,2);second['Data'][0]['ID']='0'
  with self.assertRaisesRegex(ValueError,'重复'):self.run_payloads([self.payload(100,101),second])
 def test_missing_count_remains_unconfirmed(self):
  p=self.payload(1,1);p.pop('TotalCount');r=self.run_payloads([p]);self.assertEqual(r['catalogCoverage'],'bounded-or-page-length-only');self.assertIsNone(r['reportedTotalCount'])

if __name__=='__main__':unittest.main()
