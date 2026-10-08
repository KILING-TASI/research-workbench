import unittest,copy
from security_aliases import normalize

class Aliases(unittest.TestCase):
 def spec(self):
    return {'asOf':'2026-09-30','records':[dict(id=key,market='CN-SSE',currency='CNY',assetClass='stock',shareClass='ordinary') for key in ['vendor:600519','name:贵州茅台','canonical:600519']],
            'links':[dict(left=left,right=right,relation='same-security',source='教学证券关系',publishedAt='2026-01-01',acquiredAt='2026-01-02') for left,right in [('vendor:600519','name:贵州茅台'),('name:贵州茅台','canonical:600519')]]}
 def test_transitive_aliases_do_not_mutate_records(self):
    spec=self.spec();old=copy.deepcopy(spec);result=normalize(spec)
    self.assertEqual(len(result['groups']),1);self.assertEqual(spec,old)
    self.assertEqual(len(set(result['canonicalIds'].values())),1)
 def test_ah_market_or_share_class_is_not_same_security(self):
    for key,value in [('market','HKEX'),('currency','HKD'),('shareClass','class-B')]:
        spec=self.spec();spec['records'][1][key]=value
        with self.assertRaisesRegex(ValueError,'冲突'):normalize(spec)
 def test_fund_investment_edge_is_not_equivalence(self):
    spec=self.spec();spec['links'][0]['relation']='invests-in'
    with self.assertRaisesRegex(ValueError,'same-security'):normalize(spec)
 def test_future_evidence_is_not_applied(self):
    spec=self.spec();spec['links'][0]['acquiredAt']='2026-10-01'
    result=normalize(spec);self.assertEqual(len(result['excludedLinks']),1);self.assertEqual(len(result['groups']),2)
