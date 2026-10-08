import unittest
from copy import deepcopy
from bond_topfive_concentration import calculate,check_quote_fields

class ConcentrationTests(unittest.TestCase):
    def test_bool_rank_and_malformed_grouping_rejected(self):
        s=deepcopy(self.spec);s['entries'][0]['rank']=True
        with self.assertRaises(ValueError):calculate(s)
        row=dict(rank=1,code='100000',amountCNY='100.00',reportedNAVPercentage='2.00',originalQuote='1 100000 示例债 100 1,00.00 2.00')
        with self.assertRaises(ValueError):check_quote_fields(row)
    def setUp(self):
        self.spec=dict(denominatorBasis='disclosed-bond-portfolio',bondPortfolioAmountCNY='100',entries=[dict(rank=i+1,code=f'{100000+i}',amountCNY=str(20-i),reportedNAVPercentage='10') for i in range(5)])
    def test_partial_not_whole(self):
        self.assertEqual(calculate(self.spec)['topFiveBondPortfolioPercentage'],'90.0')
    def test_missing_row(self):
        self.spec['entries'].pop()
        with self.assertRaises(ValueError):calculate(self.spec)
    def test_wrong_denominator(self):
        self.spec['denominatorBasis']='net-assets'
        with self.assertRaises(ValueError):calculate(self.spec)
    def test_order_or_duplicate(self):
        for field,value in [('amountCNY','50'),('code','100000')]:
            s=deepcopy(self.spec);s['entries'][1][field]=value
            with self.assertRaises(ValueError):calculate(s)
    def test_nonfinite_or_excess(self):
        for value in ['NaN','-1','80']:
            s=deepcopy(self.spec);s['entries'][0]['amountCNY']=value
            with self.assertRaises(ValueError):calculate(s)
    def test_substring_amount_rejected(self):
        row=dict(rank=1,code='100000',amountCNY='1.00',reportedNAVPercentage='2.00',originalQuote='1 100000 示例债 100 11.00 2.00')
        with self.assertRaises(ValueError):check_quote_fields(row)
    def test_wrong_rank_or_percentage(self):
        row=dict(rank=2,code='100000',amountCNY='11.00',reportedNAVPercentage='2.00',originalQuote='1 100000 示例债 100 11.00 2.00')
        with self.assertRaises(ValueError):check_quote_fields(row)
        row['rank']=1;row['reportedNAVPercentage']='0.00'
        with self.assertRaises(ValueError):check_quote_fields(row)
    def test_total_is_not_any_amount(self):
        row=dict(amountCNY='100.00',originalQuote='1 国家债券 100.00 99.00')
        with self.assertRaises(ValueError):check_quote_fields(row)
        row['originalQuote']='10 合计 100.00 99.00';check_quote_fields(row)

if __name__=='__main__':unittest.main()
