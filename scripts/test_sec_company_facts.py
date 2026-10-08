import unittest,tempfile
from unittest.mock import patch
from sec_company_facts import parse,period_groups,markdown,filing_directory,select_period,run
class Tests(unittest.TestCase):
 def test_external_response_redirect_rejected_before_read_and_write(self):
  from unittest.mock import MagicMock
  from pathlib import Path
  with tempfile.TemporaryDirectory() as directory:
   response=MagicMock();response.__enter__.return_value=response;response.url='https://other.example/companyfacts.json'
   with patch('sec_company_facts.urllib.request.urlopen',return_value=response):
    with self.assertRaisesRegex(ValueError,'跳转'):run('0000320193','2026-10-03',directory+'/out','Research contact@example.org')
   response.read.assert_not_called();self.assertFalse((Path(directory)/'out').exists())
 def test_versions_not_silently_chosen(self):
  rows=[dict(start='2025-01-01',end='2025-06-30',accn=a,val=v) for a,v in [('a',10),('b',12)]]
  g=period_groups(rows)[0];self.assertTrue(g['valueConflict']);self.assertEqual(g['distinctValues'],[10,12]);self.assertEqual(g['durationDays'],181)
 def test_source_locator_rejects_bad_accession(self):
  self.assertEqual(filing_directory('0000320193','0000320193-25-000001'),'https://www.sec.gov/Archives/edgar/data/320193/000032019325000001/')
  with self.assertRaises(ValueError):filing_directory('0000320193','../other')
 def test_cumulative_cross_boundary_not_quarter(self):
  r=dict(asOf='2026-10-03',metrics={'NetIncomeLoss':dict(periodGroups=[dict(start='2025-01-01',end='2025-06-30'),dict(start='2025-04-01',end='2025-06-30')])})
  x=select_period(r,'2025-04-01','2025-06-30');self.assertEqual(len(x['selectedPeriods']['NetIncomeLoss']),1);self.assertEqual(len(x['crossBoundaryPeriods']['NetIncomeLoss']),1)
 def test_invalid_query_never_downloads(self):
  cases=[('bad',None,None),('2026-10-03','2025-01-01',None),('2026-10-03','2025-06-30','2025-01-01'),('2026-10-03','2026-10-01','2026-10-04')]
  with tempfile.TemporaryDirectory() as t,patch('sec_company_facts.urllib.request.urlopen') as download:
   for cutoff,start,end in cases:
    with self.subTest(cutoff=cutoff,start=start,end=end),self.assertRaises(ValueError):
     run('0000320193',cutoff,t+'/new',None,start,end)
   download.assert_not_called()
 def sample(self):return dict(cik=320193,entityName='APPLE INC',facts={'us-gaap':{'Assets':dict(label='Assets',units={'USD':[dict(end='2025-09-30',filed='2025-11-01',val=100,accn='0000320193-25-000001',form='10-K'),dict(end='2025-09-30',filed='2026-11-01',val=200,accn='0000320193-26-000002',form='10-K/A')]})}})
 def test_filed_cutoff_not_period(self):
  r=parse(self.sample(),'0000320193','2026-10-03');self.assertEqual(len(r['metrics']['Assets']['observations']),1);self.assertTrue(r['gaps'])
 def test_raw_pointer_and_exclusion_reasons(self):
  payload=self.sample();fact=payload['facts']['us-gaap']['Assets']
  fact['units']['EUR']=[dict(val=99)]
  fact['units']['USD'].append(dict(val=50))
  r=parse(payload,'0000320193','2026-10-03');m=r['metrics']['Assets']
  self.assertEqual(m['observations'][0]['sourcePointer'],'/facts/us-gaap/Assets/units/USD/0')
  self.assertEqual(m['excludedObservations'],dict(nonUSD=1,missingDates=1,afterCutoff=1,unsupportedForm=0))
 def test_non_usd_not_zero_or_absent_tag(self):
  payload=self.sample();payload['facts']['us-gaap']['Assets']['units']={'EUR':[dict(val=99)]}
  r=parse(payload,'0000320193','2026-10-03')
  self.assertEqual(r['metrics']['Assets']['observations'],[])
  self.assertIn('EUR',r['gaps'][0]['reason'])
 def test_identity(self):
  with self.assertRaises(ValueError):parse(self.sample(),'0000000001','2026-10-03')
 def test_duration_without_start_not_instant_fact(self):
  payload=self.sample();payload['facts']['us-gaap']['NetIncomeLoss']=payload['facts']['us-gaap']['Assets']
  r=parse(payload,'0000320193','2026-10-03');self.assertEqual(r['metrics']['NetIncomeLoss']['observations'],[]);self.assertEqual(r['metrics']['NetIncomeLoss']['excludedObservations']['missingDates'],1)
 def test_filed_before_period_end_rejected(self):
  payload=self.sample();payload['facts']['us-gaap']['Assets']['units']['USD'][0]['filed']='2025-09-29'
  with self.assertRaises(ValueError):parse(payload,'0000320193','2026-10-03')
 def test_noncanonical_and_malformed_inputs(self):
  for payload,cik,asof in [(None,'0000320193','2026-10-03'),(self.sample(),True,'2026-10-03'),(self.sample(),'0000320193','20261003')]:
   with self.assertRaises(ValueError):parse(payload,cik,asof)
if __name__=='__main__':unittest.main()
