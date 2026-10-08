import unittest
from copy import deepcopy
from product_margin_bridge import calculate,check_row,check_report_period
class ProductTests(unittest.TestCase):
    def test_malformed_money_is_not_numeric_substring(self):
        for token in ['100.00%','100.00e3','1,00.00','+100.00','−100.00']:
            row=dict(revenueCNY='100.00',costCNY='70.00',quote='电网智能 '+token+' 70.00')
            with self.subTest(token=token),self.assertRaises(ValueError):check_row(row,'电网智能')
    def test_boolean_amount_and_blank_comparability_rejected(self):
        s=deepcopy(self.spec);s['periods'][0]['items']['A']['costCNY']=True
        with self.assertRaises(ValueError):calculate(s)
        s=deepcopy(self.spec);s['comparabilityNotes']=' '
        with self.assertRaises(ValueError):calculate(s)
    def setUp(self):
        old=dict(period='2025-06-30',periodBasis='half-year',items={'A':dict(revenueCNY='50',costCNY='25'),'B':dict(revenueCNY='50',costCNY='40')},total=dict(revenueCNY='100',costCNY='65'))
        new=dict(period='2026-06-30',periodBasis='half-year',items={'A':dict(revenueCNY='70',costCNY='35'),'B':dict(revenueCNY='30',costCNY='24')},total=dict(revenueCNY='100',costCNY='59'))
        self.spec=dict(currency='CNY',unit='元',groupMappingReviewed=True,comparabilityNotes='测试对应组',periods=[old,new])
    def test_mix_only(self):
        r=calculate(self.spec);self.assertEqual(r['mixContributionPercentagePoints'],'6.00');self.assertEqual(r['withinContributionPercentagePoints'],'0.00')
    def test_within_reduces_margin(self):
        self.spec['periods'][1]['items']['A']['costCNY']='42';self.spec['periods'][1]['total']['costCNY']='66';r=calculate(self.spec);self.assertEqual(r['withinContributionPercentagePoints'],'-7.00');self.assertEqual(r['changePercentagePoints'],'-1.00')
    def test_group_or_term_mismatch(self):
        for mode in ('group','term'):
            s=deepcopy(self.spec)
            if mode=='group':s['periods'][1]['items']['C']=s['periods'][1]['items'].pop('B')
            else:s['periods'][1]['periodBasis']='full-year'
            with self.assertRaises(ValueError):calculate(s)
    def test_total_mismatch(self):
        self.spec['periods'][0]['total']['costCNY']='64'
        with self.assertRaises(ValueError):calculate(self.spec)
    def test_zero_revenue_or_unreviewed(self):
        s=deepcopy(self.spec);s['groupMappingReviewed']=False
        with self.assertRaises(ValueError):calculate(s)
        self.spec['periods'][0]['items']['A']['revenueCNY']='0';self.spec['periods'][0]['total']['revenueCNY']='50'
        with self.assertRaises(ValueError):calculate(self.spec)
    def test_wrong_product_name(self):
        row=dict(revenueCNY='100.00',costCNY='70.00',quote='电网智能 100.00 70.00 30.00')
        check_row(row,'电网智能')
        with self.assertRaises(ValueError):check_row(row,'能源低碳')
    def test_swapped_or_substring_amount(self):
        for revenue,cost in [('70.00','100.00'),('0.00','70.00')]:
            row=dict(revenueCNY=revenue,costCNY=cost,quote='电网智能 100.00 70.00 30.00')
            with self.assertRaises(ValueError):check_row(row,'电网智能')
    def test_prior_pair_is_not_current_pair(self):
        row=dict(revenueCNY='90.00',costCNY='60.00',amountColumnPair='prior',quote='主营业务 100.00 70.00 90.00 60.00')
        check_row(row,'主营业务')
        row['amountColumnPair']='current'
        with self.assertRaises(ValueError):check_row(row,'主营业务')
    def test_prior_pair_requires_four_amounts(self):
        row=dict(revenueCNY='90.00',costCNY='60.00',amountColumnPair='prior',quote='主营业务 90.00 60.00')
        with self.assertRaises(ValueError):check_row(row,'主营业务')
    def test_comparative_period_matches_report(self):
        p=deepcopy(self.spec['periods'][0])
        for r in list(p['items'].values())+[p['total']]:r['amountColumnPair']='prior'
        check_report_period(p,'公司2026 年半年度报告')
        p['period']='2024-06-30'
        with self.assertRaises(ValueError):check_report_period(p,'公司2026 年半年度报告')
    def test_mixed_columns_rejected(self):
        p=deepcopy(self.spec['periods'][0]);p['items']['A']['amountColumnPair']='prior'
        with self.assertRaises(ValueError):check_report_period(p,'公司2026年半年度报告')
if __name__=='__main__':unittest.main()
