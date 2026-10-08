import unittest
from unittest.mock import patch
from refresh_public_data import refresh
from refresh_public_data import merge
from build_bjx_workbench import payload
from compare_delivery_data import compare

class Delivery(unittest.TestCase):
    def test_legacy_patch_publish_rejects_unreviewed_preserved_files(self):
        from publish_bjx_delivery import inspect_preserved_entries,task_entry
        for name in ['skill/cache/account.json','skill/docs/private.PDF','skill/.env','../outside.json']:
            with self.subTest(name=name),self.assertRaises(ValueError):inspect_preserved_entries([name])
        inspect_preserved_entries(['skill/SKILL.md','skill/scripts/run.py','skill/research/tasks/old.json'])
        self.assertTrue(task_entry('research/tasks/old.json'))
        self.assertTrue(task_entry('skill/research/tasks/old.json'))
        self.assertFalse(task_entry('research/not-tasks/old.json'))
    def test_review_detects_removal_archive_and_original_conflict(self):
        old={'records':[{'code':'1','price':10},{'code':'removed'}],'predictionArchive':[1]}
        new={'records':[{'code':'1','price':11}],'predictionArchive':[]}
        report=compare(old,new,{'records':{'1':{'officialFieldVerification':{'price':{'value':10,'status':'original-numeric-matched'}}}}})
        self.assertEqual(report['removed'],['removed']);self.assertTrue(report['requiresReview'])
        self.assertFalse(report['predictionArchivePreserved']);self.assertEqual(len(report['originalConflicts']),1)
    def test_duplicate_code_rejected(self):
        with self.assertRaises(ValueError):compare({'records':[]},{'records':[{'code':'1'},{'code':'1'}]}, {})
    def test_refresh_without_model_and_with_per_record_details(self):
        previous={'records':[], 'customResearch':{'keep':True}}
        with patch('refresh_public_data.fetch',return_value={}),patch('refresh_public_data.normalize',return_value={'records':[{'code':'1'}]}),patch('refresh_public_data.enrich') as e:
            result=refresh(previous,2)
        e.assert_called_once_with(result,previous,max_queries=2)
        self.assertTrue(result['customResearch']['keep'])
        self.assertFalse(result['modelOptimizationRun'])
        self.assertEqual(result['refreshDetails'][0]['code'],'1')
    def test_conflict_and_archive_preserved(self):
        old={'records':[{'code':'1','announcements':[{'title':'original'}],'officialFieldVerification':{'price':{'value':10}}}],'predictionArchive':[{'frozen':True}]}
        new=merge(old,{'records':[{'code':'1','price':11}]})
        self.assertEqual(new['records'][0]['announcements'],old['records'][0]['announcements'])
        self.assertEqual(new['records'][0]['sourceConflicts']['price']['originalRegistered'],10)
        self.assertFalse(new['modelOptimizationRun'])
        self.assertEqual(new['predictionArchive'],old['predictionArchive'])
    def test_future_actual_not_reference(self):
        records=[{'code':'target','applyDate':'2026-01-10','ratePct':99},{'code':'future','listingDate':'2026-01-11','ratePct':88}]+[{'code':str(i),'listingDate':'2026-01-01','ratePct':.02} for i in range(10)]
        result=payload({'records':records,'fetchedAt':'x','source':'third-party'},{'records':{}},{})
        r=result['records'][0];self.assertEqual(r['hundredReference']['rates']['中位参考'],.02)
        self.assertNotIn('target',r['hundredReference']['codes']);self.assertNotIn('future',r['hundredReference']['codes'])
        self.assertIsNone(r['issuePE']);self.assertIsNone(r['paymentDate'])
    def test_refresh_preserves_registered_precision_and_correction_review(self):
        evidence={'ratePct':{'value':.11,'status':'original-numeric-matched','precision':'disclosed-rounded'}}
        previous={'records':[{'code':'920019','officialFieldVerification':evidence,'announcementCorrectionReviews':[{'sha256':'original','status':'body-reviewed'}],'supplementalSearchEvidence':'verified-receipt','issuePE':11.19,'issuePEEvidence':{'sha256':'report'}}]}
        result=merge(previous,{'records':[{'code':'920019','ratePct':.12}]})['records'][0]
        self.assertEqual(result['officialFieldVerification'],evidence)
        self.assertEqual(result['announcementCorrectionReviews'],previous['records'][0]['announcementCorrectionReviews'])
        self.assertEqual(result['supplementalSearchEvidence'],'verified-receipt')
        self.assertEqual(result['issuePEEvidence'],{'sha256':'report'})
        self.assertEqual(result['sourceConflicts']['ratePct']['thirdParty'],.12)
        self.assertEqual(result['sourceConflicts']['ratePct']['originalRegistered'],.11)
    def test_body_date_survives_metadata_refresh_and_page_projection(self):
        from announcements import merge_links
        reviewed={'title':'发行结果公告','date':'2024-09-23','url':'https://example.invalid/result.pdf','bodyChecked':True,'bodyDate':'2024-09-23','metadataDate':'2024-09-20','dateBasis':'document body; first-public time uncertified','dateEvidence':{'page':4,'sha256':'original'}}
        incoming={**reviewed,'date':'2024-09-20','bodyChecked':False}
        links=list(merge_links([reviewed],[incoming]).values())
        result=payload({'records':[{'code':'920019','applyDate':'2024-09-18','announcements':links}],'fetchedAt':'x','source':'cached'},{'records':{}},{})['records'][0]
        self.assertEqual(result['resultDates'],['2024-09-23'])
        self.assertEqual(result['announcements'][0]['metadataDate'],'2024-09-20')
        self.assertEqual(result['announcements'][0]['dateEvidence']['page'],4)
if __name__=='__main__':unittest.main()
