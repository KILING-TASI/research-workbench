import copy
import unittest
from unittest.mock import patch
from reconcile_original_values import reconcile
from compare_delivery_data import compare


class Reconciliation(unittest.TestCase):
    def test_new_incomplete_security_still_requires_review(self):
        result=compare({'records':[]},{'records':[{'code':'920022'}]},{'records':{}})
        self.assertEqual(result['changed'],[])
        self.assertEqual(result['added'],['920022'])
        self.assertTrue(result['requiresReview'])
    def spec(self):
        data={'records':[{'code':'920196','ratePct':0.02945205}]}
        evidence={'status':'original-numeric-matched','value':0.0294520509,'sha256':'sha','page':2,'sourceUrl':'original'}
        overlays={'records':{'920196':{'officialFieldVerification':{'ratePct':evidence}}}}
        checked={'results':[{'code':'920196','field':'ratePct','status':'original-rechecked','sha256':'sha','page':2,'sourceUrl':'original'}]}
        return data,overlays,checked
    def test_only_rechecked_original_applied_and_raw_retained(self):
        data,overlays,checks=self.spec();before=copy.deepcopy(data)
        with patch('reconcile_original_values.recheck',return_value=checks):result,report=reconcile(data,overlays,'.')
        self.assertEqual(data,before);self.assertEqual(result['records'][0]['ratePct'],0.0294520509)
        self.assertEqual(result['records'][0]['thirdPartyValues']['ratePct'],0.02945205)
        self.assertEqual(result['records'][0]['sourceConflicts']['ratePct']['status'],'resolved-original-rechecked')
        self.assertFalse(result['records'][0]['fieldProvenance']['ratePct']['publicationTimeCertified'])
        self.assertEqual(report['applied'],1)
        comparison=compare(data,result,overlays)
        self.assertEqual(comparison['originalConflicts'],[]);self.assertEqual(len(comparison['resolvedOriginalDifferences']),1)
        self.assertEqual(comparison['resolvedOriginalDifferences'][0]['thirdParty'],0.02945205)
    def test_unavailable_original_does_not_resolve_conflict(self):
        data,overlays,checks=self.spec();checks['results'][0].update(status='not-verified',reason='Matching original hash unavailable')
        with patch('reconcile_original_values.recheck',return_value=checks):result,report=reconcile(data,overlays,'.')
        self.assertEqual(result['records'],data['records']);self.assertEqual(report['notApplied'],1)
    def test_reapplying_preserves_initial_provider_value(self):
        data,overlays,checks=self.spec()
        with patch('reconcile_original_values.recheck',return_value=checks):
            first,_=reconcile(data,overlays,'.');second,_=reconcile(first,overlays,'.')
        self.assertEqual(second['records'][0]['thirdPartyValues']['ratePct'],0.02945205)
    def test_duplicate_code_rejected(self):
        data,overlays,checks=self.spec();data['records']*=2
        with patch('reconcile_original_values.recheck',return_value=checks):
            with self.assertRaises(ValueError):reconcile(data,overlays,'.')
