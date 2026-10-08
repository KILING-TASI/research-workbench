import unittest
from fund_balance_snapshot import scoped_balance_label,balance_amount,column_cell
class Tests(unittest.TestCase):
 def test_same_child_kept_under_distinct_parents(self):
  key,parent=scoped_balance_label('交易性金融资产',None);a,parent=scoped_balance_label('资产支持证券投资',parent);key,parent=scoped_balance_label('债权投资',parent);b,parent=scoped_balance_label('资产支持证券投资',parent);self.assertEqual(a,'交易性金融资产/资产支持证券投资');self.assertEqual(b,'债权投资/资产支持证券投资');self.assertNotEqual(a,b)
 def test_top_level_breaks_child_scope(self):
  key,parent=scoped_balance_label('应收清算款','债权投资');self.assertEqual(key,'应收清算款');self.assertIsNone(parent)
 def test_without_parent_does_not_invent_one(self):
  key,parent=scoped_balance_label('资产支持证券投资',None);self.assertEqual(key,'资产支持证券投资');self.assertIsNone(parent)
 def test_dash_is_unknown_not_zero(self):
  for token in ['-','－','—']:self.assertIsNone(balance_amount(token))
  self.assertEqual(balance_amount('0.00'),0)
  with self.assertRaises(ValueError):balance_amount('12,34.56')
 def test_merged_amount_follows_header_coordinates(self):
  row=['资产','注','123.00',None,None,'456.00',None,None];boxes=[(0,0,10,1),(10,0,20,1),(20,0,40,1),None,None,(40,0,60,1),None,None]
  self.assertEqual(column_cell(row,boxes,30),(2,'123.00'));self.assertEqual(column_cell(row,boxes,50),(5,'456.00'))
  with self.assertRaises(ValueError):column_cell(row,boxes,80)
if __name__=='__main__':unittest.main()
