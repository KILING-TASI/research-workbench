import copy,tempfile,unittest
from decimal import Decimal
from pathlib import Path
from subscription_scenarios import evaluate,publish,markdown
from allocation_cash import calculate


class Scenarios(unittest.TestCase):
    def spec(self):
        return {'exampleType':'teaching-only','allocation':{'code':'920022','price':'25','budget':'6000000','maxShares':800000,
                'applyDate':'2026-10-12','refundDate':'2026-10-14','saleSettlementDate':'2026-10-20',
                'opportunityRatePct':'3','fees':{'commissionPct':'.03','minimumCommission':'5','taxPct':'.05','transferFeePct':'.001'}},
                'scenarios':[{'id':'高配售假设','ratePct':'.05','gainPct':'100','rateBasis':'教学假设','gainBasis':'教学假设'},
                             {'id':'低配售假设','ratePct':'.03','gainPct':'-30','rateBasis':'教学假设','gainBasis':'教学假设'}]}

    def test_no_weights_no_expected_profit_and_unknown_fragment(self):
        result=evaluate(self.spec());self.assertIsNone(result['summary']['weightedNetProfit'])
        low=result['rows'][1];self.assertEqual(low['wholeLotShares'],0)
        self.assertEqual(low['oddLotOutcome'],'unknown-not-probability')
        self.assertLess(Decimal(low['profitAfterOpportunityCost']),0)
        self.assertIn('教学输入',markdown(result))

    def test_fragment_recomputes_retained_capital_and_break_loss(self):
        result=evaluate(self.spec());low=result['rows'][1];branch=low['additionalHundredShareBranch']
        self.assertEqual(branch['wholeLotShares'],0)
        self.assertEqual(branch['allocatedSharesAssumption'],100)
        self.assertEqual(Decimal(branch['retainedPrincipal']),2500)
        self.assertEqual(Decimal(low['retainedPrincipal']),0)
        self.assertGreater(Decimal(branch['capitalDays']),Decimal(low['capitalDays']))
        self.assertLess(Decimal(branch['profitAfterOpportunityCost']),Decimal(low['profitAfterOpportunityCost']))
        self.assertIn('不是获配概率或损失界',markdown(result))

    def test_fragment_assumption_cannot_exceed_or_create_remainder(self):
        spec=self.spec()['allocation'];spec.update(ratesPct={k:'100' for k in ('P75','P50','P25')},gainPct={k:'0' for k in ('P75','P50','P25')},rateBasis='教学',additionalSharesAssumptions={'P50':100})
        with self.assertRaises(ValueError):calculate(spec)
        spec['ratesPct']={k:'.05' for k in ('P75','P50','P25')};spec['additionalSharesAssumptions']={'P50':200}
        with self.assertRaises(ValueError):calculate(spec)

    def test_explicit_joint_weights_not_independent_rate_and_gain(self):
        spec=self.spec();spec['probabilityBasis']='教学权重，不是预测概率'
        spec['scenarios'][0]['probability']='.4';spec['scenarios'][1]['probability']='.6'
        result=evaluate(spec)
        expected=sum(Decimal(row['weight'])*Decimal(row['profitAfterOpportunityCost']) for row in result['rows'])
        self.assertEqual(Decimal(result['summary']['weightedNetProfit']),expected)
        self.assertEqual(result['summary']['proportionalHundredShareScenarioWeight'],'0.4')
        spec['scenarios'][1].pop('probability')
        with self.assertRaises(ValueError):evaluate(spec)

    def test_transfer_cost_and_breakdown_sum(self):
        spec=self.spec();result=evaluate(spec);row=result['rows'][0]
        self.assertEqual(Decimal(row['saleCostBreakdown']['transferFee']),Decimal('.05'))
        self.assertEqual(sum(map(Decimal,row['saleCostBreakdown'].values())),Decimal(row['saleCosts']))
        spec['allocation']['fees']['transferFeePct']='100'
        with self.assertRaises(ValueError):evaluate(spec)

    def test_invalid_probability_and_duplicate_scenarios(self):
        for probability in ('-.1','1.1',True):
            spec=self.spec();spec['probabilityBasis']='教学';spec['scenarios'][0]['probability']=probability;spec['scenarios'][1]['probability']='.5'
            with self.assertRaises(ValueError):evaluate(spec)
        spec=self.spec();spec['scenarios'][1]['id']=spec['scenarios'][0]['id']
        with self.assertRaises(ValueError):evaluate(spec)

    def test_old_allocation_matches_zero_transfer_default(self):
        spec=self.spec();allocation=spec['allocation'];allocation['ratesPct']={k:'.05' for k in ('P75','P50','P25')};allocation['gainPct']={k:'100' for k in ('P75','P50','P25')};allocation['rateBasis']='教学'
        with_transfer=calculate(allocation)['scenarios']['P50'];allocation['fees'].pop('transferFeePct')
        without=calculate(allocation)['scenarios']['P50']
        self.assertEqual(Decimal(with_transfer['saleCosts'])-Decimal(without['saleCosts']),Decimal('.05'))

    def test_publish_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)/'report';publish(self.spec(),out)
            self.assertTrue((out/'report-manifest.json').is_file())
            with self.assertRaises(FileExistsError):publish(self.spec(),out)

    def test_announcement_cap_can_leave_all_proportional_lots_zero(self):
        spec=self.spec();spec['allocation'].update(price='15.62',budget='5000000',maxShares=266400)
        spec['scenarios']=[{'id':'历史实际比例复算','ratePct':'0.0180666733','gainPct':'0','rateBasis':'历史结果，仅机制测试','gainBasis':'零涨幅假设'}]
        result=evaluate(spec);row=result['rows'][0]
        self.assertEqual(row['wholeLotShares'],0);self.assertFalse(row['thresholdReachable'])
        self.assertEqual(row['possibleAdditionalSharesUpperBound'],100)
        self.assertEqual(result['allocationOverview']['maxShares'],266400)
        self.assertIn('余股是否获配仍未知',markdown(result))

if __name__=='__main__':unittest.main()
