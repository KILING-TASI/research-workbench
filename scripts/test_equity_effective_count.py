import unittest
from investment_intent import issuer_exposure

class EquityCount(unittest.TestCase):
 def spec(self):
  return {'asOf':'2026-09-30','intent':{},'holdings':[{'assetId':'A','assetClass':'stock','marketValue':10},{'assetId':'H','assetClass':'stock','marketValue':10},{'assetId':'bond','assetClass':'bond','marketValue':80}],
          'issuerRelations':[{'assetId':code,'issuerId':issuer,'source':'教学关系声明','publishedAt':'2026-01-01','acquiredAt':'2026-01-02'} for code,issuer in [('A','one'),('H','two'),('bond','one')]]}
 def test_bonds_do_not_change_equity_hhi(self):
  result=issuer_exposure(self.spec())['equityConcentration']
  self.assertEqual(result['effectiveIssuerCount'],'2')
  self.assertEqual(result['portfolioCoveragePct'],'20.0')
 def test_share_classes_merge_issuer_but_remain_two_positions(self):
  spec=self.spec();spec['issuerRelations'][1]['issuerId']='one'
  result=issuer_exposure(spec)['equityConcentration']
  self.assertEqual(result['issuerCount'],1);self.assertEqual(result['securityEntries'],2)
  self.assertEqual(result['effectiveIssuerCount'],'1');self.assertEqual(result['heldThroughMultipleDirectPositionsPct'],'100')
 def test_unknown_equity_keeps_partial_scope(self):
  spec=self.spec();spec['issuerRelations']=spec['issuerRelations'][1:]
  result=issuer_exposure(spec)['equityConcentration']
  self.assertEqual(result['unknownDirectEquityValue'],'10')
  self.assertEqual(result['directEquityCoveragePct'],'50.0')
