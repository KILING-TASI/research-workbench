import copy,json,unittest
from pathlib import Path
from account_benchmark_review import calculate
class TestAccountBenchmark(unittest.TestCase):
 def setUp(self):self.s=json.loads((Path(__file__).parents[1]/'references/examples/account-benchmark-teaching.json').read_text('utf-8'))
 def test_matched(self):
  r=calculate(self.s);self.assertAlmostEqual(r['accountCumulativeTwrPct'],15.5);self.assertAlmostEqual(r['accountMinusBenchmarkPercentagePoints'],3.5);self.assertTrue(all(x['contributionPct'] is None for x in r['effects']))
 def test_basis_conflicts(self):
  for key,value in [('currency','USD'),('dividends','cash-included'),('version','v2'),('start','2025-02-01')]:
   s=copy.deepcopy(self.s);s['benchmark'][key]=value
   with self.assertRaises(ValueError):calculate(s)
 def test_unknown_flows(self):
  self.s['account']['cashFlowCoverage']='unknown'
  with self.assertRaises(ValueError):calculate(self.s)
 def test_snapshot_not_account(self):
  self.s['account']['observations']=self.s['account']['observations'][-1:]
  with self.assertRaises(ValueError):calculate(self.s)
 def test_report_new_output_and_escape(self):
  import tempfile
  from account_benchmark_review import publish
  with tempfile.TemporaryDirectory() as tmp:
   self.s['effectEvidence']['cash']='<script>alert(1)</script>'
   out=Path(tmp)/'new';publish(self.s,out)
   self.assertNotIn('<script>alert(1)</script>',(out/'报告.html').read_text('utf-8'))
   with self.assertRaises(FileExistsError):publish(self.s,out)
 def test_explicit_unknown_schema_or_method(self):
  for key in ['inputSchema','methodVersion']:
   for value in [None,'future-v999']:
    s=copy.deepcopy(self.s);s[key]=value
    with self.assertRaises(ValueError):calculate(s)
