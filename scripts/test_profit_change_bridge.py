import unittest
from profit_change_bridge import bridge,REQUIRED,OTHER_ITEMS,detail_residual,paragraphs
class Tests(unittest.TestCase):
 def company(self):
  values={'revenue':(150,100),'cost':(100,70),'profit':(25,15),'salesExpense':(6,5),'managementExpense':(6,5),'researchExpense':(6,5),'financeExpense':(-2,1)}
  return dict(metadata=dict(unit='元',currency='CNY',sectorType='industrial',scope='consolidated'),metrics={k:dict(label=k,current=dict(value=a,inputs=[]),comparators=dict(yoy=dict(value=b,inputs=[]))) for k,(a,b) in values.items()})
 def test_parent_or_unspecified_scope_not_called_consolidated(self):
  c=self.company();c['metadata']['scope']='parent';self.assertEqual(bridge(c)['status'],'not-applicable')
  del c['metadata']['scope'];self.assertEqual(bridge(c)['status'],'blocked')
 def test_reconciles_and_keeps_negative_finance_cost(self):
  r=bridge(self.company());self.assertEqual(r['reconciliationDifference'],0);self.assertEqual(r['rows'][4]['amount'],3);self.assertEqual(r['rows'][5]['amount'],-10)
 def test_missing_not_zero(self):
  c=self.company();c['metrics']['salesExpense']['current']['value']=None
  self.assertEqual(bridge(c)['status'],'blocked')
 def test_financial_not_applicable(self):
  c=self.company();c['metadata']['sectorType']='financial';self.assertEqual(bridge(c)['status'],'not-applicable')
 def test_negative_cost_not_silently_normalized(self):
  c=self.company();c['metrics']['cost']['current']['value']=-100;self.assertEqual(bridge(c)['status'],'blocked')
 def test_parent_profit_not_substituted(self):
  c=self.company();del c['metrics']['profit'];c['metrics']['parentProfit']=dict(current=dict(value=25))
  self.assertEqual(bridge(c)['status'],'blocked')
 def test_detail_missing_not_zero(self):
  r=detail_residual(bridge(self.company()),[dict(key='incomeTaxExpense',current=None,prior='0')])
  self.assertEqual(r['status'],'partial-residual-detail');self.assertEqual(r['remainingResidual'],'-10');self.assertIn('incomeTaxExpense:current',r['missing'])
 def test_detail_all_selected_accounts_reconcile(self):
  items=[dict(key=k,current='10' if k=='incomeTaxExpense' else '0',prior='0') for k in OTHER_ITEMS]
  r=detail_residual(bridge(self.company()),items);self.assertEqual(r['remainingResidual'],'0');self.assertEqual(r['status'],'selected-amounts-reconciled');self.assertFalse(r['originalVerified'])
 def test_detail_rejects_duplicate_or_double_counted_expense(self):
  r=bridge(self.company());item=dict(key='otherIncome',current='1',prior='0')
  with self.assertRaises(ValueError):detail_residual(r,[item,item])
  with self.assertRaises(ValueError):detail_residual(r,[dict(item,key='salesExpense')])
 def test_missing_detail_names_visible_in_report(self):
  base=bridge(self.company());detail=detail_residual(base,[dict(key='incomeTaxExpense',current=None,prior='0')]);text='\n'.join(paragraphs(base,detail))
  self.assertIn('所得税费用（本期单季缺金额）',text);self.assertIn('信用减值损失（未提供）',text);self.assertNotIn('incomeTaxExpense',text)
 def test_detail_malformed_money_rejected_consistently(self):
  for value in ['1,00.00','1e3','10%','NaN','Infinity',' 10.00',True,10]:
   with self.subTest(value=value):
    with self.assertRaises(ValueError):detail_residual(bridge(self.company()),[dict(key='otherIncome',current=value,prior='0')])
 def test_detail_valid_grouping_preserved(self):
  r=detail_residual(bridge(self.company()),[dict(key='otherIncome',current='1,000.25',prior='900.00')]);self.assertEqual(r['rows'][0]['profitImpact'],'100.25')
 def test_reporting_period_not_labelled_single_quarter(self):
  c=self.company();c['metadata']['comparisonBasis']='same-reporting-period';r=bridge(c)
  detail=detail_residual(r,[dict(key='incomeTaxExpense',current=None,prior='0')]);text='\n'.join(paragraphs(r,detail))
  self.assertIn('本报告期与上年同一报告期比较',text);self.assertIn('本报告期缺金额',text);self.assertNotIn('本期单季',text)
 def test_unknown_comparison_basis_rejected(self):
  c=self.company();c['metadata']['comparisonBasis']='mixed-period'
  with self.assertRaises(ValueError):bridge(c)
if __name__=='__main__':unittest.main()
