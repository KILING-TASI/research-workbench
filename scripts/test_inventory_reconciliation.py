import unittest,tempfile,json
from pathlib import Path
from inventory_reconciliation import calculate,validate_boxes,cell_amount,load_spec,require_unique_quote,allowance_movement,validate_column_order,COLUMN_ORDER,quote_amounts
class Tests(unittest.TestCase):
 def test_quote_bad_grouping_and_negative_sign_not_silently_stripped(self):
  self.assertEqual(quote_amounts('原材料 1,200.00 / 1,200.00'),['1200.00',None,'1200.00'])
  for quote in ['原材料 1,,200.00','原材料 12,00.00','原材料 -12.00','原材料 −12.00','原材料 －12.00','原材料 12.001','原材料 1.20e6','原材料 1.20E+6','原材料 12.00%','原材料 12.00％']:
   with self.subTest(quote=quote),self.assertRaises(ValueError):quote_amounts(quote)
 def test_bad_amount_text_and_null_rows_report_data_error(self):
  for value in ('未知','','—','1,,200.00'):
   rows=self.rows();rows[0]['values'][0]=value
   with self.subTest(value=value),self.assertRaisesRegex(ValueError,'有效十进制数'):calculate(rows)
  for row in (None,'原材料',12):
   with self.subTest(row=row),self.assertRaisesRegex(ValueError,'分类行须为对象'):calculate([row,self.rows()[-1]])
 def test_declared_period_columns_cannot_be_reversed_or_silently_ignored(self):
  validate_column_order({});validate_column_order({'columns':COLUMN_ORDER[:]})
  for columns in (COLUMN_ORDER[3:]+COLUMN_ORDER[:3],COLUMN_ORDER[:-1],None,['期末余额']*6):
   with self.subTest(columns=columns),self.assertRaisesRegex(ValueError,'列顺序或定义不同'):validate_column_order({'columns':columns})
 def test_allowance_gross_movements_preserved(self):
  r=allowance_movement('105194582.69','34202398.72','25610236.11','113786745.30')
  self.assertEqual(r['status'],'matched');self.assertEqual(r['difference'],'0.00')
  self.assertEqual(r['inputs']['reversalOrWriteoff'],'25610236.11')
  self.assertNotIn('reversal',r['inputs'])
 def test_allowance_missing_not_zero_and_mismatch_retained(self):
  self.assertEqual(allowance_movement('10',None,'0','10')['status'],'missing')
  self.assertIsNone(allowance_movement('10','1',None,'11')['difference'])
  self.assertEqual(allowance_movement('10','5','2','14')['status'],'conflict')
 def test_allowance_invalid_amounts_rejected(self):
  for value in ('-1','NaN','Infinity','abc',1,True):
   with self.subTest(value=value),self.assertRaises(ValueError):allowance_movement('10',value,'2','8')
 def test_quote_is_unique_after_layout_whitespace_normalization(self):
  require_unique_quote('原材料 1.00','分类表\n原材料\n1.00\n注释')
  with self.assertRaisesRegex(ValueError,'多处匹配'):require_unique_quote('原材料 1.00','原材料 1.00\n原材料\n1.00')
  with self.assertRaisesRegex(ValueError,'未定位'):require_unique_quote('原材料 2.00','原材料 1.00')
  with self.assertRaises(ValueError):require_unique_quote(' ','正文')
 def test_source_relative_to_input_not_invocation_directory(self):
  with tempfile.TemporaryDirectory() as d:
   base=Path(d);folder=base/'输入';folder.mkdir();p=folder/'spec.json';p.write_text(json.dumps({'source':'../资料/report.pdf'}),encoding='utf-8')
   self.assertEqual(Path(load_spec(p)['source']),base/'资料/report.pdf')
 def test_boxes_reject_overlap_reordering_nonfinite_and_different_rows(self):
  boxes=[[i*10,10,(i+1)*10,20] for i in range(6)];validate_boxes(boxes,100,100)
  for bad in ('overlap','reorder','nan','row','outside'):
   altered=[x[:] for x in boxes]
   if bad=='overlap':altered[1][0]=9
   if bad=='reorder':altered[0],altered[1]=altered[1],altered[0]
   if bad=='nan':altered[1][0]=float('nan')
   if bad=='row':altered[1][1]=11
   if bad=='outside':altered[-1][2]=101
   with self.subTest(bad=bad),self.assertRaises(ValueError):validate_boxes(altered,100,100)
 def test_cell_blank_stays_missing_and_multiple_values_rejected(self):
  self.assertIsNone(cell_amount(' '));self.assertIsNone(cell_amount('/'));self.assertEqual(cell_amount('1,200.00'),'1200.00')
  for text in ['12.00 13.00','12.00\n13.00','—','合计 12.00','1,,200.00','12,00.00']:
   with self.assertRaises(ValueError):cell_amount(text)
 def rows(self):return [dict(name='商品',values=['12','2','10','9','1','8']),dict(name='合计',values=['12','2','10','9','1','8'])]
 def test_match_and_net_change(self):
  r=calculate(self.rows());self.assertTrue(all(x['status']=='matched' for x in r['columns']));self.assertEqual(r['rows'][0]['netChange'],'2')
 def test_blank_not_zero(self):
  rows=self.rows();rows[0]['values'][1]=None;r=calculate(rows);self.assertEqual(r['columns'][1]['status'],'missing');self.assertEqual(r['rows'][0]['periodChecks'][0]['status'],'missing')
 def test_conflicts_retained(self):
  rows=self.rows();rows[0]['values'][2]='11';r=calculate(rows);self.assertEqual(r['columns'][2]['status'],'conflict');self.assertEqual(r['rows'][0]['periodChecks'][0]['status'],'conflict')
 def test_duplicate_and_nonfinite_rejected(self):
  rows=self.rows();rows[0]['name']='合计'
  with self.assertRaises(ValueError):calculate(rows)
  rows=self.rows();rows[0]['values'][0]='NaN'
  with self.assertRaises(ValueError):calculate(rows)
