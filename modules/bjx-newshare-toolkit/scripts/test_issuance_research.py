import copy, datetime as dt, tempfile, unittest
from pathlib import Path
from issuance_research import panel,rate,graded_allocation,structure,timeline,rules,cash,counterfactual,run,snapshot,matched_review
from research_evidence import canonical,verify,package,sha
from unittest.mock import patch

def node(id='a',metric='ratePct',value='1',unit='%',**kw):
    return {'id':id,'subject':'920022','metric':metric,'kind':'original','value':value,'unit':unit,'basis':'final',
        'page':1,'sourceUrl':'https://www.bse.cn/test','documentSha256':'0'*64,'publishedAt':'2025-01-01',
        'verification':'original-text-matched',**kw}
def allocation(code='920022'):
    return {'code':code,'price':'10','budget':'100000','maxShares':100000,'ratesPct':{'P75':'2','P50':'1','P25':'.5'},
        'rateBasis':'synthetic','gainPct':dict.fromkeys(['P75','P50','P25'],'0'),'applyDate':'2025-01-02','refundDate':'2025-01-04','saleSettlementDate':'2025-01-10'}
def declarations():return {k:{'grade':'C','value':v,'basis':'explicit-test-assumption'} for k,v in allocation()['ratesPct'].items()}

class Tests(unittest.TestCase):
    def test_company_card_cutoff_must_match_integrated_research(self):
        import json
        for asof in ['2024-12-31','2026-01-01',None]:
            with self.subTest(asof=asof),tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'company.json'
                path.write_text(json.dumps({'type':'bjx-company-research-card','code':'920022','asOf':asof}),encoding='utf-8')
                with self.assertRaisesRegex(ValueError,'截止日'):run({'code':'920022','asOf':'2025-01-02','evidence':{'companyResult':str(path)}})
    def test_unknown_blocks_allocation(self):
        d=declarations();d['P50']={'grade':'D'}
        self.assertIsNone(graded_allocation({'allocation':allocation(),'rateEvidence':d},{})['scenarios'])
    def test_grade_c(self):
        r=graded_allocation({'allocation':allocation(),'rateEvidence':declarations()},{})
        self.assertEqual(r['result']['scenarios']['P50']['wholeLotShares'],100)
    def test_grade_a_original_only(self):
        self.assertEqual(rate({'grade':'A','value':'1','basis':'actual','evidenceIds':['a']},{'a':node()})['ratePct'],'1')
        bad=node();bad['verification']='exact-text-excerpt-not-semantic-numeric-validation'
        with self.assertRaises(ValueError):rate({'grade':'A','value':'1','basis':'actual','evidenceIds':['a']},{'a':bad})
    def test_actual_blocked_predecision(self):
        with self.assertRaises(ValueError):rate({'grade':'A','value':'1','basis':'actual','evidenceIds':['a']},{'a':node()},'predecision')
    def test_a_wrong_value_and_future(self):
        for value,asof in [('2','2025-01-02'),('1','2024-01-01')]:
            with self.assertRaises(ValueError):rate({'grade':'A','value':value,'basis':'actual','evidenceIds':['a']},{'a':node()},asof=asof)
    def test_grade_b_formula(self):
        nodes={'o':node('o','onlineFinalShares','10000','股'),'t':node('t','validSubscriptionShares','1000000','股')}
        spec={'grade':'B','basis':'actual-quantity-ratio','onlineShares':'10000','validSubscriptionShares':'1000000',
            'onlineEvidenceIds':['o'],'totalEvidenceIds':['t'],'quantityBasis':'final'}
        self.assertEqual(rate(spec,nodes)['ratePct'],'1.00')
        spec['quantityBasis']='initial'
        with self.assertRaises(ValueError):rate(spec,nodes)
    def test_grade_b_no_oversubscription(self):
        with self.assertRaises(ValueError):rate({'grade':'B','basis':'test','onlineShares':'200','validSubscriptionShares':'100'}, {})
    def test_panel_missing_conflict_quality(self):
        n=node('a','price','10','元/股');m={**n,'id':'b','value':'11'}
        r=panel({'code':'920022','fields':['price','maxShares']},{'nodes':[n,m]})
        self.assertEqual(r['quality']['conflictCount'],1);self.assertEqual(r['quality']['missingCount'],1)
        self.assertEqual(r['quality']['coveragePct'],'0')
    def test_panel_usage_not_inferred(self):
        n=node('a','price','10','元/股')
        r=panel({'code':'920022','fields':['price']},{'nodes':[n]})
        self.assertFalse(r['fields'][0]['usedInCalculation'])
    def struct(self):
        def x(v,u):return {'value':str(v),'unit':u,'kind':'assumption','basis':'test'}
        return {'price':x(10,'元/股'),'preIssueShares':x(1000,'股'),'initialIssueShares':x(200,'股'),
            'initialOnlineShares':x(150,'股'),'strategicShares':x(50,'股'),'overallocatedShares':x(30,'股'),
            'actualNewShares':x(10,'股'),'actualRepurchasedShares':x(20,'股'),'adjustedProfit':x(100,'CNY'),'overallotmentDestination':'online'}
    def test_struct_views(self):
        r=structure(self.struct(),{});self.assertEqual([x['postIssueShares'] for x in r['views']],['1200','1230','1210'])
        self.assertEqual(r['onlineSharesAfterOverallotment'],'180')
    def test_struct_negative_profit_no_pe(self):
        s=self.struct();s['adjustedProfit']['value']='-100';self.assertIsNone(structure(s,{})['views'][0]['adjustedPe'])
    def test_struct_inconsistent_implementation(self):
        s=self.struct();s['actualNewShares']['value']='11'
        with self.assertRaises(ValueError):structure(s,{})
    def test_struct_unknown_actual(self):
        s=self.struct();s.pop('actualNewShares');self.assertIsNone(structure(s,{})['views'][2]['postIssueShares'])
    def test_derive_preissue_shares_from_original_post(self):
        s=self.struct();s.pop('preIssueShares');s['postIssueSharesBefore']={'value':'1200','unit':'股','kind':'assumption','basis':'test'}
        self.assertEqual(structure(s,{})['views'][0]['postIssueShares'],'1200')
    def test_timeline_unknown_and_conditional(self):
        s={'asOf':'2025-01-02','events':[{'id':'lock','subject':'investor','type':'unlock','date':None,'evidenceIds':['a']},
            {'id':'green','subject':'issuer','type':'greenshoe','date':'2025-01-30','conditions':['implementation-needed'],'evidenceIds':['a']}]}
        r=timeline(s,{'a':node()});self.assertEqual(r['missingDates'],['lock']);self.assertEqual(r['events'][0]['status'],'conditional-date')
    def test_timeline_future_evidence_rejected(self):
        with self.assertRaises(ValueError):timeline({'asOf':'2024-01-01','events':[{'id':'x','subject':'s','type':'x','evidenceIds':['a']}]},{'a':node()})
    def test_rule_difference_isolation(self):
        s={'asOf':'2025-02-01','before':'old','after':'new','selected':'new','versions':[
            {'id':'old','publishedAt':'2025-01-01','effectiveDate':'2025-01-01','reviewed':True,'parameters':{'cap':30},'evidenceIds':['a']},
            {'id':'new','publishedAt':'2025-01-02','effectiveDate':'2025-03-01','reviewed':True,'parameters':{'cap':50},'evidenceIds':['a']}],
            'impactMap':{'cap':['strategicShares']}}
        r=rules(s,{'a':node()});self.assertFalse(r['selectedApplicable']);self.assertFalse(r['automaticRuleReplacement']);self.assertEqual(r['changes'][0]['affectedFields'],['strategicShares'])
    def test_pending_rule_not_applicable(self):
        s={'asOf':'2025-01-02','selected':'x','versions':[{'id':'x','parameters':{},'evidenceIds':['a']}]}
        self.assertFalse(rules(s,{'a':node()})['selectedApplicable'])
    def test_cash_daily_and_delayed_availability(self):
        a=allocation();a.update(rateEvidence=declarations(),refundAvailableDate='2025-01-05',availabilityEvidenceIds=['a'])
        r=cash({'totalFunds':'100000','issues':[a]}, {'a':node()})
        self.assertEqual(len(r['daily']['P50']),9);self.assertEqual(r['daily']['P50'][2]['occupiedPrincipal'],'100000')
        self.assertEqual(r['dateEvidence'][0]['announcedRefundDate'],'2025-01-04')
    def test_cash_same_day_without_proof(self):
        a=allocation();a['rateEvidence']=declarations()
        with self.assertRaises(ValueError):cash({'totalFunds':'100000','issues':[a],'sameDayReleasedFundsUsable':True},{})
    def test_cash_grade_required(self):
        with self.assertRaises(ValueError):cash({'totalFunds':'100000','issues':[allocation()]},{})
    def test_counterfactual_not_write_original(self):
        a=allocation();saved=copy.deepcopy(a)
        r=counterfactual({'baseline':a,'changes':[{'field':'budget','value':'200000','category':'input','evidenceIds':['a']}]},{'a':node()})
        self.assertEqual(a,saved);self.assertEqual(r['interventions'][0]['delta']['P50']['wholeLotShares'],'100')
        self.assertFalse(r['eligibleForModelImprovement'])
    def test_counterfactual_unsupported_blocked(self):
        with self.assertRaises(ValueError):counterfactual({'baseline':allocation(),'changes':[{'field':'anything','value':1,'category':'input','evidenceIds':['a']}]},{'a':node()})
    def test_run_future_and_subject_mismatch(self):
        for s in [{'code':'920022','asOf':'2024-01-01','evidence':{'nodes':[node()]}},
            {'code':'920022','asOf':'2025-01-02','evidence':{'code':'920111'}}]:
            with self.assertRaises(ValueError):run(s)
    def test_run_and_portable_snapshot(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);rule=p/'rule.json';rule.write_text('{}');inp=p/'spec.json';out=p/'result.json'
            s={'code':'920022','asOf':'2025-01-02','evidence':{},'allocationResearch':{'allocation':allocation(),'rateEvidence':declarations()},
                'snapshot':{'mode':'historical-replay','dependencies':[{'path':str(rule),'role':'rule'}]}}
            inp.write_bytes(canonical(s));r=run(s);out.write_bytes(canonical(r));receipt=snapshot(s,r,inp,out,p)
            rule.unlink();inp.unlink();out.unlink();self.assertTrue(verify(receipt['packagePath'])['verified'])
    def test_matched_empty_and_missing_package(self):
        self.assertEqual(matched_review({'before':[],'after':[]})['commonCount'],0)
        r=matched_review({'before':[{'reviewPath':'missing-review'}],'after':[]})
        self.assertEqual(len(r['evidenceEligibilityExclusions']),1)
    def test_matched_frozen_fixture_and_rule_scope_change(self):
        from prediction_review import capture,review
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);rule=p/'rule.txt';rule.write_text('synthetic rule fixture');calc=p/'calc.json';calc.write_text('{}')
            n=node();n['documentSha256']=sha(rule.read_bytes())
            research={'code':'920022','asOf':'2025-01-01','comparisonScope':'whole-lot-funds',
                'rules':{'versions':[{'id':'v1','reviewed':True,'publishedAt':'2025-01-01','effectiveDate':'2025-01-01','parameters':{},'evidenceIds':['a']}],'selected':'v1'}}
            inp=p/'input.json';inp.write_bytes(canonical(research));cutoff='2025-01-02T09:15:00+00:00';time=dt.datetime(2025,1,1,12,tzinfo=dt.timezone.utc)
            spec={'modelVersion':'fixture','decisionCutoff':cutoff,'allocation':allocation(),
                'inputs':[{'path':str(inp),'availableAt':time.isoformat(),'retrievedAt':time.isoformat()}]}
            with patch('prediction_review.now',return_value=time):capture(spec,p)
            pred=p/'research-data/bjx-predictions/frozen/fixture/920022/first.json'
            with patch('research_evidence.now',return_value=time):
                snap=package({'mode':'predecision','decisionCutoff':cutoff,'evidence':{'nodes':[n]},'dependencies':[
                    {'path':str(inp),'role':'research-input','availableAt':time.isoformat()},
                    {'path':str(rule),'role':'rule','availableAt':time.isoformat()},
                    {'path':str(calc),'role':'calculation-result','availableAt':time.isoformat()}]},p)
            actual=p/'actual.txt';actual.write_text('synthetic actual fixture')
            with patch('prediction_review.now',return_value=dt.datetime(2025,1,12,tzinfo=dt.timezone.utc)):
                review({'predictionPath':str(pred),'actual':{'code':'920022','publishedAt':'2025-01-11T00:00:00+00:00','ratePct':'1','sourcePath':str(actual)}},p)
            rev=next((p/'research-data/bjx-reviews').glob('*.json'));item={'predictionPath':str(pred),'reviewPath':str(rev),'packagePath':snap['packagePath']}
            self.assertEqual(matched_review({'before':[item],'after':[item]})['commonCount'],1)
            research['comparisonScope']='different-scope';inp.write_bytes(canonical(research))
            with patch('research_evidence.now',return_value=time):
                changed=package({'mode':'predecision','decisionCutoff':cutoff,'evidence':{'nodes':[n]},'dependencies':[
                    {'path':str(inp),'role':'research-input','availableAt':time.isoformat()},
                    {'path':str(rule),'role':'rule','availableAt':time.isoformat()},
                    {'path':str(calc),'role':'calculation-result','availableAt':time.isoformat()}]},p)
            self.assertEqual(matched_review({'before':[item],'after':[{**item,'packagePath':changed['packagePath']}]})['commonCount'],0)

if __name__=='__main__':unittest.main()
