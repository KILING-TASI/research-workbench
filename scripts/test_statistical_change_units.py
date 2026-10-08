import unittest
from statistical_change_units import interpret
class Tests(unittest.TestCase):
 legend={'*':'absolute','▲':'percentage-point'}
 def test_star_overrides_percent_header_and_keeps_source_unit(self):
  r=interpret('-113*','小时',self.legend,'percent');self.assertEqual((r['value'],r['changeType'],r['changeUnit']),('-113','absolute','小时'))
  r=interpret('-14114*','万千瓦',self.legend,'percent');self.assertEqual(r['changeUnit'],'万千瓦')
 def test_triangle_and_unmarked_percentage_are_distinct(self):
  self.assertEqual(interpret('-0.07▲','%',self.legend,'percent')['changeUnit'],'百分点');self.assertEqual(interpret('10.8','万千瓦',self.legend,'percent')['changeUnit'],'%')
 def test_missing_not_zero_and_unknown_marker_rejected(self):
  self.assertIsNone(interpret('—','小时',self.legend,'percent')['value'])
  for token in ['-113?','113**','NaN','1,,200*']:
   with self.subTest(token=token),self.assertRaises(ValueError):interpret(token,'小时',self.legend,'percent')
 def test_source_legend_and_default_required(self):
  with self.assertRaises(ValueError):interpret('1','小时',self.legend,None)
  with self.assertRaises(ValueError):interpret('1*','小时',{'*':'guessed'},'percent')
