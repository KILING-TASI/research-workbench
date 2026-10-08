import math,unittest
from annual_yield import hand_distribution,single

class Tests(unittest.TestCase):
    def test_second_moment_matches_survival_identity(self):
        p=hand_distribution(12500000,18,5500000,.15)
        direct=sum(k*k*v for k,v in p)
        survival=sum((2*k-1)*sum(v for j,v in p if j>=k) for k in range(1,len(p)))
        self.assertAlmostEqual(direct,survival,places=9)
    def test_reported_moments_and_zero_probability(self):
        fees=dict(comm_rate=0,comm_min=0,stamp=0,transfer=0,slippage=0)
        r=single(5500000,dict(p0=18,a_star=5500000,sigma_pct=.15,r=2),fees,.02,2)
        self.assertGreater(r['handsStandardDeviation'],0)
        self.assertAlmostEqual(r['zeroProportionalHandsProbability'],.5,places=8)
        self.assertAlmostEqual(r['handsStandardDeviation']**2,r['handsSecondMoment']-r['expectedHands']**2)
    def test_zero_and_deterministic_amount(self):
        self.assertEqual(hand_distribution(0,18,5500000,.15),[(0,1)])
        self.assertEqual(hand_distribution(11000000,18,5500000,0),[(2,1)])
    def test_threshold_unit_counterexample(self):
        self.assertEqual(100*137.5e8/2.5e7,55000)

if __name__=='__main__':unittest.main()
