import unittest,tempfile,json,hashlib
from pathlib import Path
from research_workflow import context,run_template,impact

class Tests(unittest.TestCase):
 def prepare(self,p):
  ctx=context(dict(sessionId='fof',baseCurrency='CNY',frequency='trading_day',dividendTreatment='reinvest',asOf='2026-10-05',benchmark=None,riskFreeRate=.01,annualization=252,missingData='common_dates',timezone='Asia/Shanghai'))
  node=dict(currency='CNY',sourceUrl='https://example.com/report.pdf',reportDate='2025-12-31',publishedAt='2026-03-31',holdings=[dict(kind='stock',id='CN:600000',weight=.4),dict(kind='fund',node='missing',weight=.3)])
  spec=dict(asOf='2026-10-05',currency='CNY',root='root',nodes={'root':node})
  for name,obj in [('context',ctx),('input',spec)]: (p/(name+'.json')).write_text(json.dumps(obj),encoding='utf8')
  return dict(template='fof-lookthrough-review',contextPath=str(p/'context.json'),inputPath=str(p/'input.json'))
 def test_unknown_not_cash_or_renormalized(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);r=run_template(self.prepare(p),p)
   self.assertAlmostEqual(r['result']['knownWeight'],.4);self.assertAlmostEqual(r['result']['unknownWeight'],.6)
   self.assertEqual(r['result']['assetExposure']['cash'],0);self.assertEqual(r['status'],'calculated-with-gaps')
   self.assertEqual(len(r['gaps']),2)
 def test_context_mismatch(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);m=self.prepare(p);s=json.loads((p/'input.json').read_text());s['currency']='USD';(p/'input.json').write_text(json.dumps(s))
   with self.assertRaises(ValueError):run_template(m,p)
 def test_source_change_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);m=self.prepare(p);raw=p/'report.pdf';raw.write_bytes(b'changed');s=json.loads((p/'input.json').read_text());s['sourceFiles']=[dict(path=str(raw),sha256=hashlib.sha256(b'old').hexdigest())];(p/'input.json').write_text(json.dumps(s))
   with self.assertRaises(ValueError):run_template(m,p)
if __name__=='__main__':unittest.main()
