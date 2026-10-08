import math,unittest
import numpy as np
from bootstrap_diagnostics import stationary_next,quantile_precision

class Tests(unittest.TestCase):
    def test_normal_precision_matches_asymptotic_reference(self):
        r=quantile_precision(np.random.default_rng(24).normal(size=30000))
        density=math.exp(-1.644853626951**2/2)/math.sqrt(2*math.pi)
        reference=math.sqrt(.95*.05/30000)/density
        self.assertLess(abs(r['monteCarloStandardError']/reference-1),.2)
    def test_discrete_and_small_tail_does_not_fake_precision(self):
        self.assertIsNone(quantile_precision(np.zeros(2000))['monteCarloStandardError'])
        self.assertIsNone(quantile_precision(np.arange(100))['monteCarloStandardError'])
    def test_stationary_continuation_wrap_and_iid_restart(self):
        class Continue:
            def random(self,n):return np.ones(n)
            def integers(self,lo,hi,size):return np.zeros(size,dtype=int)
        self.assertEqual(stationary_next(Continue(),np.array([0,4]),5,20).tolist(),[1,0])
        rng=np.random.default_rng(42)
        out=stationary_next(rng,np.zeros(20000,dtype=int),5,1)
        counts=np.bincount(out,minlength=5)/len(out)
        self.assertTrue(np.all(abs(counts-.2)<.015))
    def test_joint_simulation_is_reproducible_and_keeps_scope(self):
        import json
        from pathlib import Path
        from portfolio_models import simulate
        spec=json.loads((Path(__file__).resolve().parents[1]/'references/examples/example-allocation.json').read_text('utf-8'))
        spec.update(weights=[1/3]*3,paths=600,steps=24,blockLength=6,bootstrapMethod='stationary')
        first=simulate(spec);second=simulate(spec)
        self.assertEqual(first,second)
        self.assertEqual(first['bootstrapMethod'],'stationary')
        self.assertEqual(first['method'],'历史联合平稳自举')
        self.assertEqual(first['blockLengthMeaning'],'expected-geometric-length')
        self.assertEqual(first['maxDrawdownP95Precision']['probability'],.95)
        self.assertEqual(first['maxDrawdownP95Precision']['paths'],600)

if __name__=='__main__':unittest.main()
