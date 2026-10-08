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
 def test_other_code_rejected(self):
  with self.assertRaises(ValueError):select([dict(FUNDCODE='000001')],'005827','2026-10-03','contract')
if __name__=='__main__':unittest.main()
