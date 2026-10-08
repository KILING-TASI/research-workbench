import unittest
from copy import deepcopy
from bond_topfive_parent import aggregate
class ParentTests(unittest.TestCase):
    def test_empty_children_not_zero_risk(self):
        for children in [[],None,[None]]:
            with self.subTest(children=children),self.assertRaises(ValueError):aggregate('100',children)
    def setUp(self):
        top=dict(denominatorBasis='disclosed-bond-portfolio',bondPortfolioAmountCNY='100',entries=[dict(rank=i+1,code=str(100000+i),amountCNY='10',reportedNAVPercentage='10') for i in range(5)])
        self.child=dict(childCode='000001',parentHoldingAmountCNY='20',childNetAssetsCNY='100',topFive=top)
    def test_same_bond_across_children_added(self):
        other=deepcopy(self.child);other['childCode']='000002'
        r=aggregate('100',[self.child,other]);self.assertEqual(len(r['securities']),5);self.assertEqual(r['totalSelectedParentNAVPercentage'],'20.00')
    def test_repeated_share_rejected(self):
        with self.assertRaises(ValueError):aggregate('100',[self.child,self.child])
    def test_bad_child_nav(self):
        self.child['childNetAssetsCNY']='0'
        with self.assertRaises(ValueError):aggregate('100',[self.child])
    def test_not_rounded_parent_weight(self):
        r=aggregate('300',[self.child]);self.assertTrue(r['totalSelectedParentNAVPercentage'].startswith('3.333333'))
if __name__=='__main__':unittest.main()
