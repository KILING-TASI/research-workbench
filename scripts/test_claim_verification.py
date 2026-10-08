import unittest,tempfile,json,hashlib
from pathlib import Path
from claim_verification import verify,pointer,markdown
class Tests(unittest.TestCase):
 def test_pointer_cannot_use_python_negative_or_noncanonical_indexes(self):
  for path in ['/-1','/01','/+1','/2','/~2']:
   with self.subTest(path=path),self.assertRaises(ValueError):pointer([10,20],path)
  self.assertEqual(pointer({'a/b':[10]},'/a~1b/0'),10)
 def test_failed_evidence_remains_readable(self):
  r=verify(dict(asOf='2026-10-05',claims=[dict(id='1',text='待核数字',kind='numeric',evidence=[{}])]))
  self.assertIn('核对失败',markdown(r));self.assertEqual(r['claims'][0]['status'],'insufficient')
 def test_bad_hash_unknown_and_scope_mismatch(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'facts.json';p.write_text('{"v":115.67478}')
   scope=dict(entity='002910',metric='return',period='2025-12-31/2026-09-30',unit='pct')
   e=dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),pointer='/v',scope=scope,publishedAt='2026-09-30',sourceUrl='https://example.org')
   c=dict(id='1',text='收益',kind='numeric',scope=scope,value=115.67,evidence=[e])
   self.assertEqual(verify(dict(asOf='2026-10-05',claims=[c]))['claims'][0]['status'],'supported')
   e['scope']={**scope,'unit':'ratio'}
   self.assertEqual(verify(dict(asOf='2026-10-05',claims=[c]))['claims'][0]['status'],'insufficient')
   e['scope']=scope;e['sha256']='0'*64
   self.assertEqual(verify(dict(asOf='2026-10-05',claims=[c]))['claims'][0]['status'],'insufficient')
 def test_rank_and_cause_not_confirmed_without_identification(self):
  r=verify(dict(asOf='2026-10-05',claims=[dict(id='1',text='冠军',kind='ranking'),dict(id='2',text='减持使回撤变小',kind='causal')]))
  self.assertTrue(all(x['status']=='insufficient' for x in r['claims']))
if __name__=='__main__':unittest.main()
