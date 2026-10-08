import unittest
import numpy as np
from covariance_shrinkage import estimate

class Tests(unittest.TestCase):
    def test_two_assets_target_equals_sample(self):
        data=np.random.default_rng(3).normal(size=(100,2));cov,meta=estimate(data)
        self.assertTrue(np.allclose(cov,np.cov(data,rowvar=False)));self.assertEqual(meta['status'],'sample-equals-target')
    def test_variances_psd_scale_and_permutation(self):
        data=np.random.default_rng(4).normal(size=(300,4));cov,meta=estimate(data)
        self.assertTrue(0<=meta['intensity']<=1);self.assertTrue(np.allclose(np.diag(cov),np.diag(np.cov(data,rowvar=False))))
        self.assertGreaterEqual(np.linalg.eigvalsh(cov).min(),-1e-12)
        reordered,_=estimate(data[:,[2,0,3,1]]);self.assertTrue(np.allclose(reordered,cov[np.ix_([2,0,3,1],[2,0,3,1])]))
        scaled,details=estimate(data*.01);self.assertTrue(np.allclose(scaled,cov*.0001));self.assertAlmostEqual(details['intensity'],meta['intensity'])
    def test_zero_variance_missing_and_small_sample_rejected(self):
        for data in (np.ones((30,2)),np.ones((10,3)),[[float('nan'),1]]*30):
            with self.assertRaises(ValueError):estimate(data)
