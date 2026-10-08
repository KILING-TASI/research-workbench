import unittest
from copy import deepcopy
from fund_holder_units_review import calculate,disclosed_number,explicit_flow_residual,strict_json
class HolderTests(unittest.TestCase):
    def test_duplicate_json_and_nonfinite_rejected(self):
        for raw in ['{"code":"000001","code":"000002"}','{"entries":[{"totalUnits":1,"totalUnits":2}]}','{"value":NaN}','{"value":Infinity}']:
            with self.subTest(raw=raw),self.assertRaises(ValueError):strict_json(raw)
        self.assertEqual(strict_json('{"value":null}'),{'value':None})

    def test_dash_is_not_automatically_zero(self):
        with self.assertRaises(ValueError):disclosed_number('-')
        self.assertEqual(disclosed_number('-','assumed-zero-for-explicit-dash'),0)
        for token in ['', '1,00.00','1e3','10%']:
            with self.subTest(token=token),self.assertRaises(ValueError):disclosed_number(token)
        self.assertEqual(disclosed_number('10%',percentage=True),10)
    def setUp(self):
        self.h=dict(code='000001',reportDate='2026-06-30',sourceSha256='test',entries=[dict(shareClass='基金A',institutionUnits='2',personalUnits='8',totalUnits='10',reportedInstitutionPercentage='20',reportedPersonalPercentage='80')])
        self.f=dict(code='000001',reportDate='2026-06-30',sourceSha256='test',flowRows={k:dict(label=l,values=[v]) for k,l,v in [('opening','期初','20'),('subscription','申购','5'),('redemption','赎回','15'),('split','拆分','0'),('closing','期末','10')]})
    def test_explicit_residual_keeps_unknown_split(self):
        self.f['flowRows']['split']['values']=['-'];r=explicit_flow_residual(self.f,['A']);self.assertEqual(r['classes'][0]['unexplainedNetShareMovement'],'0');self.assertIsNone(r['classes'][0]['splitReportedValue']);self.assertFalse(r['classes'][0]['splitEventAbsenceVerified'])
        with self.assertRaises(ValueError):calculate(self.h,self.f,['A'])
    def test_explicit_nonzero_residual_is_not_silenced(self):
        self.f['flowRows']['closing']['values']=['11'];r=explicit_flow_residual(self.f,['A']);self.assertEqual(r['classes'][0]['unexplainedNetShareMovement'],'1');self.assertFalse(r['classes'][0]['explicitFieldsNetConsistent'])
    def test_explicit_missing_values_not_zero(self):
        self.f['flowRows']['redemption']['values']=['-']
        with self.assertRaises(ValueError):explicit_flow_residual(self.f,['A'])
    def test_units_are_not_cash(self):
        r=calculate(self.h,self.f,['A']);self.assertEqual(r['classes'][0]['netShareChangeUnits'],'-10');self.assertNotIn('netFlowCNY',r)
    def test_wrong_denominator(self):
        self.h['entries'][0]['personalUnits']='7'
        with self.assertRaises(ValueError):calculate(self.h,self.f,['A'])
    def test_wrong_ratio(self):
        self.h['entries'][0]['reportedInstitutionPercentage']='30'
        with self.assertRaises(ValueError):calculate(self.h,self.f,['A'])
    def test_missing_or_wrong_label(self):
        for mode in ('missing','label'):
            f=deepcopy(self.f)
            if mode=='missing':del f['flowRows']['split']
            else:f['flowRows']['subscription']['label']='赎回'
            with self.assertRaises(ValueError):calculate(self.h,f,['A'])
    def test_signed_split(self):
        self.f['flowRows']['split']['values']=['-1'];self.f['flowRows']['closing']['values']=['9'];h=self.h['entries'][0];h.update(institutionUnits='3',personalUnits='6',totalUnits='9',reportedInstitutionPercentage='33.33',reportedPersonalPercentage='66.67');calculate(self.h,self.f,['A'])
    def test_total_not_double_counted(self):
        total=dict(self.h['entries'][0],shareClass='合计');self.h['entries'].append(total);self.assertEqual(len(calculate(self.h,self.f,['A'])['classes']),1)
    def test_wrong_total_rejected(self):
        self.h['entries'].append(dict(self.h['entries'][0],shareClass='合计',totalUnits='11'))
        with self.assertRaises(ValueError):calculate(self.h,self.f,['A'])
    def test_string_or_empty_share_order_rejected(self):
        for order in ['A',[],[''],[None],['A','A']]:
            with self.assertRaises(ValueError):calculate(self.h,self.f,order)
    def test_overflow_json_not_parsed_as_infinity(self):
        with self.assertRaises(ValueError):strict_json('{"value":1e999}')
if __name__=='__main__':unittest.main()
