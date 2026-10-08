import unittest
import numpy as np
from returns_style import fit

class Style(unittest.TestCase):
 def test_sum_constraint_can_identify_proportional_benchmarks(self):
    x=np.linspace(-.01,.01,200);benchmarks=np.column_stack([x,2*x])
    result=fit(benchmarks@np.array([.7,.3]),benchmarks)
    self.assertEqual(result['centeredFactorRank'],1)
    self.assertEqual(result['constrainedDesignRank'],2)
    self.assertFalse(result['weightIdentificationWarning'])
    np.testing.assert_allclose(result['weights'],[.7,.3],atol=1e-8)
 def test_recovers_known_mix_and_ignores_constant_mean_residual(self):
    rng=np.random.default_rng(4);x=rng.normal(0,.01,(200,2));y=x@np.array([.7,.3])+.002
    result=fit(y,x)
    np.testing.assert_allclose(result['weights'],[.7,.3],atol=1e-8)
    self.assertAlmostEqual(result['rSquaredVariance'],1)
    self.assertAlmostEqual(result['meanResidual'],.002)
 def test_collinear_weights_are_flagged(self):
    x=np.linspace(-.02,.02,200);result=fit(x,np.column_stack([x,x]))
    self.assertTrue(result['weightIdentificationWarning'])
    self.assertAlmostEqual(sum(result['weights']),1)
 def test_outside_pool_does_not_become_negative_weights(self):
    rng=np.random.default_rng(2);x=rng.normal(0,.01,(200,2));y=-x[:,0]
    result=fit(y,x)
    self.assertTrue(all(weight>=0 for weight in result['weights']))
    self.assertAlmostEqual(sum(result['weights']),1)
