import unittest
import numpy as np
from portfolio_risk_diagnostics import covariance_diagnostics,risk_concentration

class Tests(unittest.TestCase):
    def test_bad_matrices_and_observation_counts_are_rejected(self):
        for matrix in ([[1,2,3],[1,2,3]],[[1,float('nan')],[0,1]]):
            with self.assertRaises(ValueError):covariance_diagnostics(matrix,np.eye(2),25)
        for n in [0,True,1.5]:
            with self.assertRaises(ValueError):covariance_diagnostics(np.eye(2),np.eye(2),n)
        with self.assertRaises(ValueError):covariance_diagnostics(np.eye(2),np.eye(2),25,{'intensity':2})
        with self.assertRaises(ValueError):risk_concentration([[.5,.5]])
    def test_equal_risk_and_concentrated_risk(self):
        self.assertAlmostEqual(risk_concentration([.1]*10)['effectiveRiskContributors'],10)
        self.assertLess(risk_concentration([.45,.45]+[.0125]*8)['effectiveRiskContributors'],2.5)
    def test_negative_and_zero_contributions_not_mislabelled(self):
        self.assertIsNone(risk_concentration([1.2,-.2])['effectiveRiskContributors'])
        self.assertIsNone(risk_concentration(None)['effectiveRiskContributors'])
        with self.assertRaises(ValueError):risk_concentration([.3,.3])
    def test_condition_and_shrinkage_are_not_probability(self):
        s=np.ones((2,2));d=covariance_diagnostics(s,np.eye(2),25,{'intensity':.8})
        self.assertTrue(d['sampleConditionNumber'] is None or d['sampleConditionNumber']>1e8)
        self.assertEqual(d['estimatedConditionNumber'],1)
        self.assertEqual(len(d['warnings']),2)
    def test_scale_does_not_change_condition(self):
        s=np.array([[1,.3],[.3,2]])
        a=covariance_diagnostics(s,s,100);b=covariance_diagnostics(s*1e-16,s*1e-16,100)
        self.assertAlmostEqual(a['sampleConditionNumber'],b['sampleConditionNumber'])

if __name__=='__main__':unittest.main()
