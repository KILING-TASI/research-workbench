import unittest
from macro_asset_observation import validate_series_contract,parse_csv,changes,SERIES
class Tests(unittest.TestCase):
 def test_units_and_frequencies_reject_wrong_definition(self):
  for id,field,value in [('DCOILWTICO','unit','USD'),('PCOPPUSDM','frequency','daily-business'),('PCOPPUSDM','unit','USD-per-pound')]:
   s=dict(id=id,**SERIES[id]);s[field]=value
   with self.assertRaises(ValueError):validate_series_contract([s],check_frequency=True)
 def test_copper_monthly_is_macro_not_asset_return(self):
  s=dict(id='PCOPPUSDM',**SERIES['PCOPPUSDM']);self.assertEqual(validate_series_contract([s],True)[0]['status'],'supported-definition-checked');self.assertEqual(s['role'],'macro')
 def test_negative_wti_not_rejected_or_used_as_positive_return_base(self):
  raw=b'observation_date,DCOILWTICO\n2020-04-20,-36.98\n2020-04-21,9.12\n';points,_=parse_csv(raw,'DCOILWTICO','2020-04-01','2020-04-30');s=dict(id='DCOILWTICO',**SERIES['DCOILWTICO'],points=points,status='available');self.assertEqual(changes(s)['recentObservationWindows'][0]['status'],'nonpositive-base')
 def test_negative_copper_rejected(self):
  with self.assertRaisesRegex(ValueError,'无效'):parse_csv(b'observation_date,PCOPPUSDM\n2026-01-01,-1\n','PCOPPUSDM','2026-01-01','2026-02-01')
if __name__=='__main__':unittest.main()
