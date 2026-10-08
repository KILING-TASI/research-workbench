import unittest,tempfile,hashlib,copy
from pathlib import Path
from unittest.mock import patch
from disclosed_rate_scenario import calculate,parent_weight_evidence
class Tests(unittest.TestCase):
 def test_parent_amount_weight_binding_rejects_changed_weight(self):
  from decimal import Decimal
  with tempfile.TemporaryDirectory() as d:
   s,reader=self.fixture(d);reader.pages[0].extract_text=lambda:'父持仓20.00 父净资产100.00'
   e=dict(reportDate='2026-06-30',holdingAmountCNY='20.00',parentNetAssetsCNY='100.00',path=s['source']['path'],sha256=s['source']['sha256'],locators=[dict(page=1,quote='父持仓20.00',field='holdingAmountCNY'),dict(page=1,quote='父净资产100.00',field='parentNetAssetsCNY')])
   with patch('pypdf.PdfReader',return_value=reader):r=parent_weight_evidence(e,'2026-06-30',Decimal('.2'),Path('.'))
   self.assertEqual(r['status'],'selected-amounts-located-weight-recomputed')
   with self.assertRaisesRegex(ValueError,'复算不一致'):parent_weight_evidence(e,'2026-06-30',Decimal('.3'),Path('.'))
 def test_rate_quote_direction_and_percent_conversion(self):
  with tempfile.TemporaryDirectory() as d:
   s,reader=self.fixture(d);s['source']['locators'][1]['quote']='利率增加0.25%上升-5.00';s['scenarios'][0]['reportedRateChangeBasisPoints']=s['scenarios'][0].pop('parallelShiftBasisPoints')
   reader.pages[0].extract_text=lambda:'净资产100.00 利率增加0.25%上升-5.00 下降6.00'
   with patch('pypdf.PdfReader',return_value=reader):r=calculate(s)
   self.assertEqual(r['scenarios'][0]['shockEvidence']['rateChangeBasisPoints'],'25.00')
   s['scenarios'][0]['reportedRateChangeBasisPoints']=-25
   with patch('pypdf.PdfReader',return_value=reader),self.assertRaisesRegex(ValueError,'方向或基点'):calculate(s)
 def test_shapes_and_unverified_shock_scope(self):
  for s in [None,[],{},dict(source={},scenarios=[None])]:
   with self.assertRaises(ValueError):calculate(s)
  with tempfile.TemporaryDirectory() as d:
   s,reader=self.fixture(d)
   with patch('pypdf.PdfReader',return_value=reader):r=calculate(s)
   self.assertEqual(r['scenarios'][0]['shockVerification'],'input-declared-not-original-verified')
 def fixture(self,d):
  p=Path(d)/'report.pdf';p.write_bytes(b'fixture');s=dict(currency='CNY',reportDate='2026-06-30',publishedAt='2026-08-31',childNetAssetsCNY='100.00',parentWeight='.2',assumptions=['其他变量不变'],scenarios=[dict(parallelShiftBasisPoints=25,navImpactCNY='-5.00'),dict(parallelShiftBasisPoints=-25,navImpactCNY='6.00')],source=dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),locators=[dict(page=1,quote='净资产100.00',field='childNetAssetsCNY'),dict(page=1,quote='上升-5.00',field='scenarios/0/navImpactCNY'),dict(page=1,quote='下降6.00',field='scenarios/1/navImpactCNY')]))
  class Page:
   def extract_text(self):return '净资产100.00 上升-5.00 下降6.00'
  class Reader:pages=[Page()]
  return s,Reader()
 def test_asymmetric_original_scenarios_preserved(self):
  with tempfile.TemporaryDirectory() as d:
   s,reader=self.fixture(d)
   with patch('pypdf.PdfReader',return_value=reader):r=calculate(s)
   self.assertEqual(r['scenarios'][0]['isolatedParentImpactFraction'],'-0.01');self.assertEqual(r['scenarios'][1]['isolatedParentImpactFraction'],'0.012')
 def test_reported_shock_not_relabelled_parallel(self):
  with tempfile.TemporaryDirectory() as d:
   s,reader=self.fixture(d)
   for x in s['scenarios']:x['reportedRateChangeBasisPoints']=x.pop('parallelShiftBasisPoints')
   with patch('pypdf.PdfReader',return_value=reader):r=calculate(s)
   self.assertEqual(r['scenarios'][0]['shockDefinition'],'reportedRateChangeBasisPoints')
 def test_conflicting_shock_definition_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   s,reader=self.fixture(d);s['scenarios'][0]['reportedRateChangeBasisPoints']=10
   with patch('pypdf.PdfReader',return_value=reader),self.assertRaisesRegex(ValueError,'冲击口径'):calculate(s)
 def test_changed_amount_not_supported_by_quote(self):
  with tempfile.TemporaryDirectory() as d:
   s,reader=self.fixture(d);s['scenarios'][0]['navImpactCNY']='-50.00'
   with patch('pypdf.PdfReader',return_value=reader),self.assertRaisesRegex(ValueError,'对应原文'):calculate(s)
 def test_missing_amount_locator_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   s,reader=self.fixture(d);s['source']['locators'][0].pop('field')
   with patch('pypdf.PdfReader',return_value=reader),self.assertRaisesRegex(ValueError,'对应原页'):calculate(s)
if __name__=='__main__':unittest.main()

