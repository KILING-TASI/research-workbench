import unittest
from portfolio_class_constraints import solve

class Tests(unittest.TestCase):
    def test_covariance_scale_does_not_change_weights(self):
        import numpy as np
        matrix=np.diag([.01,.02,.1]);classes=['equity','equity','bond'];bounds={'equity':{'min':0,'max':.4}}
        reference=solve(matrix,classes,bounds)
        for factor in (1e-18,1e18):
            result=solve(matrix*factor,classes,bounds)
            self.assertTrue(np.allclose(result['weights'],reference['weights'],atol=1e-8))
    def test_tiny_indefinite_covariance_is_not_accepted_by_absolute_tolerance(self):
        with self.assertRaises(ValueError):solve([[1e-20,2e-20],[2e-20,1e-20]],['equity','bond'],{'equity':{'min':0,'max':1}})
    def test_target_is_enforced_and_equal_mean_is_not_false_infeasibility(self):
        value=solve([[1,0],[0,1]],['equity','bond'],{'equity':{'min':0,'max':.7}},mean=[.1,.2],target=.16)
        self.assertAlmostEqual(value['weights'][0],.4,places=7)
        same=solve([[1,0],[0,1]],['equity','bond'],{'equity':{'min':0,'max':.7}},mean=[.1,.1],target=.1)
        self.assertAlmostEqual(sum(same['weights']),1)
    def test_equity_cap_changes_solution(self):
        result=solve([[.01,0,0],[0,.02,0],[0,0,.1]],['equity','equity','bond'],{'equity':{'min':0,'max':.4}})
        self.assertAlmostEqual(sum(result['weights']),1);self.assertAlmostEqual(result['classWeights']['equity'],.4,places=7)
        self.assertAlmostEqual(result['weights'][2],.6,places=7)
    def test_contradictory_groups_rejected(self):
        with self.assertRaises(ValueError):solve([[1,0],[0,1]],['equity','bond'],{'equity':{'min':.7,'max':1},'bond':{'min':.7,'max':1}})
    def test_unknown_class_rejected(self):
        with self.assertRaises(ValueError):solve([[1,0],[0,1]],['equity','bond'],{'gold':{'min':0,'max':.2}})
    def test_asset_lower_bound_enforced(self):
        result=solve([[.01,0],[0,1]],['equity','bond'],{'equity':{'min':0,'max':1}},lower=.3,upper=.7)
        self.assertAlmostEqual(result['weights'][0],.7,places=7);self.assertAlmostEqual(result['weights'][1],.3,places=7)
