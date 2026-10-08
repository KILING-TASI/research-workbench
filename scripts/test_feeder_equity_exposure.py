import unittest,tempfile,hashlib
from pathlib import Path
from decimal import Decimal
from feeder_equity_exposure import build
class Tests(unittest.TestCase):
 def test_parent_holdings_identity_cannot_differ_from_report(self):
  for key,value in [('id','000002'),('reportDate','2025-06-30'),('sourceUrl','https://other.example/r')]:
   with tempfile.TemporaryDirectory() as directory:
    r=self.fixture(directory);r['report']['holdings'][key]=value
    with self.assertRaisesRegex(ValueError,'身份或日期'):build(r)
 def test_bad_stock_rows_not_hidden_by_valid_totals(self):
  for key,value in [('locator',None),('name',[]),('marketValueCNY','NaN'),('shareClass',{})]:
   with tempfile.TemporaryDirectory() as t:
    r=self.fixture(t);r['targetReport']['holdings']['holdings'][0][key]=value
    with self.subTest(key=key),self.assertRaises(ValueError):build(r)
 def test_string_verified_is_not_verification(self):
  with tempfile.TemporaryDirectory() as t:
   r=self.fixture(t);r['fundInvestmentAccounting']['accountingTotalVerified']='false'
   with self.assertRaises(ValueError):build(r)
 def test_duplicate_child_security_rows_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   r=self.fixture(t);h=r['targetReport']['holdings'];h['holdings']*=2;h['equityMarketValueCNY']=200
   with self.assertRaisesRegex(ValueError,'明细重复'):build(r)
 def fixture(self,t):
  def report(code,name,nav,equity):
   p=Path(t)/(code+'.pdf');p.write_bytes(code.encode());sha=hashlib.sha256(p.read_bytes()).hexdigest()
   return dict(code=code,reportDate='2025-12-31',asOf='2026-10-03',identityStatus='matched',status='副本身份及股票持仓勾稽完成',documentPath=str(p),sha256=sha,metadata=dict(title=name+'2025年年报',publishedAt='2026-03-31',sourceUrl='https://example.org/'+code),holdings=dict(id=code,reportDate='2025-12-31',publishedAt='2026-03-31',sourceUrl='https://example.org/'+code,sourceSha256=sha,netAssetsCNY=nav,equityMarketValueCNY=equity,holdings=[dict(code='600001',securityNamespace='CN-equity',name='同一股票',marketValueCNY=equity,locator='PDF页10')]))
  parent=report('000001','联接基金',100,10);child=report('510001','目标ETF',200,100)
  return dict(report=parent,targetReport=child,targetFundLink=dict(target=dict(code='510001',name='目标ETF'),reportDate=parent['reportDate'],asOf=parent['asOf'],publishedAt='2026-03-31',sourceSha256=parent['sha256'],limitations=[]),fundInvestmentAccounting=dict(sourceSha256=parent['sha256'],reportDate=parent['reportDate'],asOf=parent['asOf'],accountingTotalVerified=True,netAssetsCNY='100',rows=[dict(name='目标ETF',marketValueCNY='80')]))
 def test_overlap_and_unexpanded(self):
  with tempfile.TemporaryDirectory() as t:
   r=build(self.fixture(t));self.assertEqual(len(r['rows']),1);self.assertEqual(Decimal(r['knownEquityWeight']),Decimal('0.5'));self.assertEqual(Decimal(r['unexpandedNAVResidual']),Decimal('0.5'));self.assertEqual(len(r['rows'][0]['parts']),2);self.assertFalse(r['completeAssetPortfolio'])
 def test_alias_not_guessed(self):
  with tempfile.TemporaryDirectory() as t:
   r=self.fixture(t);r['fundInvestmentAccounting']['rows'][0]['name']='目标简称'
   with self.assertRaises(ValueError):build(r)
 def test_total_not_verified(self):
  with tempfile.TemporaryDirectory() as t:
   r=self.fixture(t);r['fundInvestmentAccounting']['accountingTotalVerified']=False
   with self.assertRaises(ValueError):build(r)
 def test_changed_stock_sum(self):
  with tempfile.TemporaryDirectory() as t:
   r=self.fixture(t);r['targetReport']['holdings']['equityMarketValueCNY']=101
   with self.assertRaises(ValueError):build(r)
 def test_mixed_parent_cutoff(self):
  with tempfile.TemporaryDirectory() as t:
   r=self.fixture(t);r['report']['asOf']='2026-09-30'
   with self.assertRaises(ValueError):build(r)
 def test_changed_source(self):
  with tempfile.TemporaryDirectory() as t:
   r=self.fixture(t);r['fundInvestmentAccounting']['sourceSha256']='different'
   with self.assertRaises(ValueError):build(r)
if __name__=='__main__':unittest.main()
