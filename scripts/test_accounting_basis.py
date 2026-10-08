import unittest
from accounting_basis import validate,paragraphs
class Tests(unittest.TestCase):
 def test_qualified_negative_audit_quote_is_not_positive(self):
  for state,quote in [('audited','本半年度财务报告未经会计师事务所审计。'),('reviewed','本期财务报表未经独立会计师审阅。')]:
   report=dict(fileSha256='teaching',pages=[dict(page=1,text=quote)])
   with self.subTest(state=state),self.assertRaises(ValueError):validate(dict(auditStatus=state,evidence=[dict(page=1,quote=quote)]),report)
  quote='本半年度财务报告未经会计师事务所审计。'
  self.assertEqual(validate(dict(auditStatus='unaudited',evidence=[dict(page=1,quote=quote)]),dict(fileSha256='teaching',pages=[dict(page=1,text=quote)]))['auditStatus'],'unaudited')
 def test_missing_context_not_called_unaudited(self):
  self.assertIn('尚未核对',str(paragraphs(None)));self.assertNotIn('未经审计',str(paragraphs(None)))
 def test_unbacked_audit_claim_rejected(self):
  for c in [dict(auditStatus='audited'),dict(auditStatus='reviewed'),dict(framework='企业会计准则')]:
   with self.assertRaises(ValueError):validate(c,{})
 def test_invalid_status_and_framework_rejected(self):
  for c in [dict(auditStatus='certified'),dict(framework='')]:
   with self.assertRaises(ValueError):validate(c,{})
 def test_unknown_does_not_assert_compliance(self):
  r=validate({},{});self.assertEqual(r['status'],'not-reviewed');self.assertEqual(r['auditStatus'],'unknown')
if __name__=='__main__':unittest.main()
