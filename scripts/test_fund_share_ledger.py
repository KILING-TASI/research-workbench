import unittest
from fund_share_ledger import parse,run
class Tests(unittest.TestCase):
 def test_malformed_table(self):
  for value in [None,{},[None]*6]:
   with self.subTest(value=value),self.assertRaises(ValueError):parse(value)
 def test_invalid_request_rejected_before_pdf_read(self):
  from unittest.mock import patch
  spec=dict(path='not-read.pdf',sha256='a'*64,code='159915',start='2026-01-01',end='2026-06-30',page=22)
  for key,value in [('code',159915),('start','20260101'),('start','2026-07-01'),('sha256','wrong'),('page',True),('dashPolicy','guess')]:
   with self.subTest(key=key),patch('fund_share_ledger.Path.read_bytes') as read,self.assertRaises(ValueError):run(dict(spec,**{key:value}),'.')
   read.assert_not_called()
 def rows(self):return [['项目','本期',None],[None,'基金份额（份）','账面金额'],['上年度末','100.00','80.00'],['本期申购','20.00','16.00'],['本期赎回（以“-”号填列）','-40.00','-32.00'],['本期末','80.00','64.00']]
 def test_quantity_not_money(self):self.assertEqual(parse(self.rows())['netShareChange'],'-20.00')
 def test_wrong_header(self):
  r=self.rows();r[1][1],r[1][2]=r[1][2],r[1][1]
  with self.assertRaises(ValueError):parse(r)
 def test_extra_event(self):
  r=self.rows();r.append(['拆分','0.00','0.00'])
  with self.assertRaises(ValueError):parse(r)
 def test_nonreconciled(self):
  r=self.rows();r[-1][1]='81.00'
  with self.assertRaises(ValueError):parse(r)
 def test_wrong_redemption_sign(self):
  r=self.rows();r[-2][1]='40.00'
  with self.assertRaises(ValueError):parse(r)
 def test_dash_requires_assumption(self):
  r=self.rows();r[3][1]='-';r[-1][1]='60.00'
  with self.assertRaises(ValueError):parse(r)
  out=parse(r,'assumed-zero-for-explicit-dash');self.assertEqual(out['status'],'conditional-reconciliation-with-dash-assumption');self.assertEqual(out['dashRows'],['subscription'])
 def test_blank_never_zero(self):
  r=self.rows();r[3][1]='';r[-1][1]='60.00'
  with self.assertRaises(ValueError):parse(r,'assumed-zero-for-explicit-dash')
 def test_mixed_redemption_label_rejected(self):
  for label in ['本期赎回与拆分（以“-”号填列）','本期赎回调整（以“-”号填列）']:
   r=self.rows();r[-2][0]=label
   with self.assertRaises(ValueError):parse(r)
if __name__=='__main__':unittest.main()
