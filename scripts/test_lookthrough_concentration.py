import unittest
from research_extensions import fof

class Lookthrough(unittest.TestCase):
 def test_alias_merge_keeps_original_paths_and_repeated_routes(self):
  spec=self.spec();spec['issuerRelations']=[]
  spec['securityAliases']={'records':[dict(id=key,market='CN-SSE',currency='CNY',assetClass='stock',shareClass='ordinary') for key in ['A','H']],
                          'links':[dict(left='A',right='H',relation='same-security',source='教学别名关系',publishedAt='2026-07-20',acquiredAt='2026-07-21')]}
  result=fof(spec)
  self.assertAlmostEqual(result['leaves']['A'],.5)
  self.assertEqual(result['securityConcentration']['securityCount'],2)
  self.assertTrue(any(trace['path'][-1]=='H' and trace['canonicalSecurityId']=='A' for trace in result['paths']))
 def spec(self):
  metadata={'currency':'CNY','sourceUrl':'https://example.org/report','reportDate':'2026-06-30','publishedAt':'2026-07-20'}
  return {'asOf':'2026-09-30','currency':'CNY','root':'portfolio','nodes':{
   'portfolio':dict(metadata,holdings=[{'kind':'fund','node':'feeder','weight':.5},{'kind':'stock','id':'A','weight':.2}]),
   'feeder':dict(metadata,holdings=[{'kind':'fund','node':'etf','weight':1}]),
   'etf':dict(metadata,holdings=[{'kind':'stock','id':'H','weight':.6},{'kind':'stock','id':'B','weight':.4}])},
   'issuerRelations':[{'assetId':key,'issuerId':issuer,'source':'教学证券关系','publishedAt':'2026-07-20','acquiredAt':'2026-07-21'} for key,issuer in [('A','company-one'),('H','company-one'),('B','company-two')]]}
 def test_nested_fund_weights_and_issuer_merge_preserve_unknown(self):
  result=fof(self.spec());c=result['equityConcentration']
  self.assertAlmostEqual(result['leaves']['H'],.3)
  self.assertEqual(c['issuerCount'],2);self.assertEqual(c['securityEntries'],3)
  self.assertAlmostEqual(float(c['effectiveIssuerCount']),49/29)
  self.assertAlmostEqual(c['unresolvedPortfolioWeightPct'],30)
  self.assertAlmostEqual(float(c['portfolioCoveragePct']),70)
 def test_no_mapping_does_not_invent_company_count(self):
  spec=self.spec();spec.pop('issuerRelations')
  c=fof(spec)['equityConcentration']
  self.assertIsNone(c['effectiveIssuerCount']);self.assertEqual(c['issuerCount'],0)
 def test_same_security_through_two_funds_counts_as_repeated_route(self):
  spec=self.spec()
  spec['nodes']['portfolio']['holdings']=[{'kind':'fund','node':'feeder','weight':.5},{'kind':'fund','node':'etf','weight':.5}]
  spec['issuerRelations']=[relation for relation in spec['issuerRelations'] if relation['assetId']!='A']
  c=fof(spec)['equityConcentration']
  self.assertEqual(c['securityEntries'],2)
  self.assertAlmostEqual(c['heldThroughMultipleRootPositionsPct'],100)
  for position in c['positionDiagnostics']:
   self.assertAlmostEqual(position['replicatedByOtherKnownEquityPct'],100)
   self.assertAlmostEqual(position['uniqueCompanyShareOfOwnKnownEquityPct'],0)
 def test_no_unique_names_does_not_imply_identical_weights(self):
  spec=self.spec();metadata={key:value for key,value in spec['nodes']['etf'].items() if key!='holdings'}
  spec['nodes']['second']=dict(metadata,holdings=[{'kind':'stock','id':'H','weight':.1},{'kind':'stock','id':'B','weight':.9}])
  spec['nodes']['portfolio']['holdings']=[{'kind':'fund','node':'etf','weight':.5},{'kind':'fund','node':'second','weight':.5}]
  spec['issuerRelations']=[relation for relation in spec['issuerRelations'] if relation['assetId']!='A']
  rows=fof(spec)['equityConcentration']['positionDiagnostics']
  self.assertTrue(all(row['uniqueCompanyShareOfOwnKnownEquityPct']==0 for row in rows))
  self.assertTrue(all(abs(row['replicatedByOtherKnownEquityPct']-50)<1e-8 for row in rows))
