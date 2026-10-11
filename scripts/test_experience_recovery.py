import unittest,tempfile,json
from pathlib import Path
from research_question import run
from _offline_security_catalog import prepare
class Recovery(unittest.TestCase):
    def test_unprefixed_name_and_multiple_names(self):
        calls=[]
        def identity(*args):calls.append(args[1]);return {'rows':[], 'coverage':[{'status':'missing-local-catalog'}]}
        with tempfile.TemporaryDirectory() as d:
            r=run({'question':'贵州茅台最近三个月有哪些值得关注的公告','asOf':'2026-10-11'},d,identity)
            self.assertEqual(calls,['贵州茅台']);self.assertEqual(r['failureKind'],'missing-local-catalog');self.assertIn('贵州茅台',r['answer'])
            r=run({'question':'贵州茅台和招商银行最近三个月的公告','asOf':'2026-10-11'},d,identity)
            self.assertEqual(r['status'],'needs-clarification');self.assertEqual(len(calls),1)
    def test_explicit_catalog_ambiguous_name_and_cutoff(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'catalog.json';value={'sourceUrl':'https://example.org/declared-teaching-directory','asOf':'2026-10-01','rows':[{'code':'900001','name':'教学公司','exchange':'SSE'},{'code':'900002','name':'教学公司','exchange':'SZSE'}]};f.write_text(json.dumps(value),encoding='utf-8')
            r=run({'question':'教学公司最近三个月公告','asOf':'2026-10-11','catalog':str(f)},d)
            self.assertEqual(r['status'],'needs-clarification');self.assertIsNone(r['resolvedSecurity']);self.assertEqual(len(r['identitySearch']['rows']),2)
            value['asOf']='2026-10-12';f.write_text(json.dumps(value),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'晚于'):prepare(f,d,'2026-10-11')
    def test_single_catalog_candidate_is_not_official_certification(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'catalog.json';f.write_text(json.dumps({'sourceUrl':'https://example.org/teaching','asOf':'2026-10-01','rows':[{'code':'900001','name':'教学公司','exchange':'SSE'}]}),encoding='utf-8')
            r=run({'question':'教学公司近三个月公告','asOf':'2026-10-11','catalog':str(f),'refresh':False,'items':[]},d)
            self.assertEqual(r['resolvedSecurity']['identityVerification'],'catalog-not-officially-verified');self.assertEqual(r['status'],'data-unavailable')
if __name__=='__main__':unittest.main()
