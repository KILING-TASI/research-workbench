import unittest
from report_industry_threshold import amount
class Tests(unittest.TestCase):
 def test_classification_and_duplicate_sectors_rejected(self):
  import tempfile,hashlib,copy
  from pathlib import Path
  from report_industry_threshold import run
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory)/'report.pdf';p.write_bytes(b'fixture');h=hashlib.sha256(p.read_bytes()).hexdigest()
   report=dict(code='000001',reportDate='2026-06-30',asOf='2026-10-06',metadata=dict(publishedAt='2026-08-31',sourceUrl='https://example.org/r'),sha256=h,documentPath=str(p),identityStatus='declared')
   industries=dict(code='000001',reportDate=report['reportDate'],publishedAt='2026-08-31',sourceSha256=h,sourceUrl='https://example.org/r',netAssetsCNY='100',equityMarketValueCNY='30',taxonomy='test',taxonomyVersion='1',sectors=[dict(key='A',name='行业',marketValueCNY='30',components=[])])
   spec=dict(asOf='2026-10-06',minimumWeightPctOfNAV=30,industryKey='A',dossier=dict(code='000001',asOf='2026-10-06',report=report,reportIndustries=industries))
   self.assertTrue(run(spec)['passed'])
   bad=copy.deepcopy(spec);bad['dossier']['reportIndustries']['taxonomyVersion']=''
   with self.assertRaisesRegex(ValueError,'分类体系'):run(bad)
   bad=copy.deepcopy(spec);bad['dossier']['reportIndustries']['sectors']*=2
   with self.assertRaisesRegex(ValueError,'重复'):run(bad)
 def test_nonfinite_negative_and_boolean_rejected(self):
  for value in ['NaN','Infinity','-1',True,'not-amount']:
   with self.subTest(value=value),self.assertRaises(ValueError):amount(value)
 def test_zero_nav_rejected_but_empty_sector_allowed(self):
  self.assertEqual(amount('0'),0)
  with self.assertRaises(ValueError):amount('0',positive=True)
if __name__=='__main__':unittest.main()
