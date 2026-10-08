import unittest
from fund_legal_evidence import build
class Tests(unittest.TestCase):
 def test_pending_identity_does_not_count_as_matched(self):
  s=self.spec();s['dossier']['report']['metadata']['title']='某基金年报';s['dossier']['report']['identityStatus']='pending'
  with self.assertRaisesRegex(ValueError,'已核验报告'):build(s)
 def test_blank_name_does_not_match_every_title(self):
  s=self.spec();s['fundFullName']=' '
  with self.assertRaises(ValueError):build(s)
 def spec(self):return dict(fundFullName='某基金',dossier=dict(code='000001',asOf='2026-10-03',report=dict(code='000001',asOf='2026-10-03',identityStatus='matched',metadata=dict(title='其他基金年报'))),amendmentArchive=dict(asOf='2026-10-03'))
 def test_name_mismatch_rejected(self):
  with self.assertRaises(ValueError):build(self.spec())
 def test_cutoff_mismatch_rejected(self):
  s=self.spec();s['amendmentArchive']['asOf']='2026-09-01'
  with self.assertRaises(ValueError):build(s)
if __name__=='__main__':unittest.main()
