import copy,json,math,unittest
from pathlib import Path
from annual_yield import evaluate,single,hand_distribution,load_calendar,repo_days,market_scenario,access_check,regime_checks,markdown


class Annual(unittest.TestCase):
    def spec(self):return json.loads((Path(__file__).resolve().parents[1]/'assets/example-annual-yield.json').read_text('utf-8'))
    def test_account_declaration_required_and_whitespace_cannot_hide_duplicates(self):
        spec=self.spec();spec.pop('accounts')
        self.assertEqual(evaluate(spec)['status'],'blocked-eligibility')
        spec['accounts']=[{'identityKey':'same'},{'identityKey':' same '}]
        self.assertEqual(evaluate(spec)['status'],'blocked-eligibility')
        spec['accounts']=[{'identityKey':'   '}]
        with self.assertRaises(ValueError):evaluate(spec)
    def test_blocked_report_answers_how_to_continue_without_fake_numbers(self):
        spec=self.spec();spec['eligibility']['bsePermission']=False
        result=evaluate(spec);body=markdown(result)
        self.assertIn('接下来怎样继续',body);self.assertIn('不需要填写完整JSON',body)
        self.assertIn('未计算时不提供收益区间',body);self.assertIsNone(result['scenarios'])
    def test_five_weekday_repo_days_and_holiday(self):
        calendar=load_calendar(2026)
        for start,end,expected in [('2026-10-12','2026-10-14',2),('2026-10-13','2026-10-15',2),('2026-10-14','2026-10-16',4),('2026-10-15','2026-10-19',4),('2026-10-16','2026-10-20',2)]:
            self.assertEqual(repo_days(start,end,calendar)[0],expected)
        days,rows=repo_days('2026-09-30','2026-10-09',calendar)
        self.assertEqual(days,4)
        self.assertEqual([(r['firstSettlementDate'],r['maturitySettlementDate'],r['accrualDays']) for r in rows],[('2026-10-08','2026-10-09',1),('2026-10-09','2026-10-12',3)])
        with self.assertRaises(ValueError):repo_days('2026-10-10','2026-10-12',calendar)
        with self.assertRaises(ValueError):load_calendar(2027)

    def test_commission_is_max_not_added_minimum(self):
        scenario={'p0':25,'a_star':500000,'sigma_pct':0,'r':1}
        fees={'comm_rate':.0025,'comm_min':5,'stamp':0,'transfer':0,'slippage':0}
        result=single(500000,scenario,fees,0,2)
        self.assertEqual(result['expectedHands'],1)
        self.assertEqual(result['sellCost'],12.5)
        self.assertEqual(result['netProfit'],2487.5)

    def test_probability_mass_and_physical_hand_limit(self):
        for capital in [0,1800,3000000,12500000]:
            distribution=hand_distribution(capital,18,5500000,.15)
            self.assertAlmostEqual(sum(p for _,p in distribution),1)
            self.assertTrue(all(k<=int(capital/1800) and p>=0 for k,p in distribution))
        with self.assertRaises(ValueError):hand_distribution(10000,18,1700,.15)

    def test_consistency_and_two_inputs(self):
        row=self.spec()['scenarios']['neutral'];row['allocationRatio']=.01
        with self.assertRaises(ValueError):market_scenario(row)
        row['allocationRatio']=100*18/5500000;row.pop('p0')
        self.assertAlmostEqual(market_scenario(row)['p0'],18)

    def test_gate_before_calculation_and_duplicate_identity(self):
        spec={'eligibility':{'bsePermission':False}}
        self.assertEqual(evaluate(spec)['status'],'blocked-eligibility')
        spec=self.spec();spec['accounts']*=2
        self.assertFalse(access_check(spec)['passed'])
        spec=self.spec();spec['eligibility']['starPermission']=True;spec['eligibility'].pop('averageAssets20TradingDays');spec['eligibility'].pop('experienceMonths')
        self.assertTrue(access_check(spec)['passed'])

    def test_regime_missing_not_safe_and_two_breaks_trigger(self):
        spec=self.spec();self.assertEqual(regime_checks(spec,.03)['status'],'insufficient-observations')
        spec['recentListings']=[{'code':str(i),'listingDate':f'2026-09-{i+1:02d}','firstDayReturn':-.1 if i<2 else .2,'source':'教学样本'} for i in range(5)]
        spec['recentListingsComplete']=True
        self.assertEqual(regime_checks(spec,.03)['status'],'reassess-under-declared-thresholds')

    def test_report_contains_required_sections_and_no_unverified_claim(self):
        result=evaluate(self.spec());body=markdown(result)
        for term in ('毛收益','假设与收益敏感性','资金成本','口径与风险','不构成投资建议','其他用途','阶段性重新评估'):self.assertIn(term,body)
        self.assertTrue(result['postRefundCostIncluded']);self.assertEqual(result['postRefundCostDays'],5)
        self.assertTrue(all(math.isfinite(row['annualNet']) for row in result['scenarios'].values()))
        self.assertIn('尚不能证明这笔资金全年放在打新更合适',body)
        self.assertIn('不是组合增量收益',body)

    def test_idle_cost_and_funding_clamp(self):
        spec=self.spec();spec['cash_alternative']='idle';spec['s_in_transit']='9000000'
        result=evaluate(spec)
        self.assertEqual(result['availableCapital'],1000000)
        self.assertTrue(all(row['atAvailableCap']['subscriptionAmount']<=1000000 for row in result['scenarios'].values()))

if __name__=='__main__':unittest.main()
