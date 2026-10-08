import unittest,tempfile,json
from pathlib import Path
from fund_batch_screen import run,candidate_metrics
class Tests(unittest.TestCase):
 def test_ranking_rendered_and_missing_rank_explained(self):
  with tempfile.TemporaryDirectory() as root:
   spec=self.spec();p=Path(root)/'rank';r=run(spec,p,fetch=lambda u:self.text(u.split('/')[-1][:6]))
   self.assertEqual(len(r['rankingGroups']),1);text=(p/'筛选简报.md').read_text(encoding='utf-8');self.assertIn('组内序号',text);self.assertIn('2025-01-01/2025-01-05',text)
   spec['rank']['field']='aumCNY';p=Path(root)/'missing';r=run(spec,p,fetch=lambda u:self.text(u.split('/')[-1][:6]))
   self.assertEqual(len(r['rankingGaps']),2);self.assertIn('未进入排序：排序指标缺失',(p/'筛选简报.md').read_text(encoding='utf-8'))
 def text(self,c):return 'var fS_code='+json.dumps(c)+';var fS_name="测试";var Data_netWorthTrend='+json.dumps([{'x':1735689600000+i*86400000,'y':1+i*.01,'unitMoney':''} for i in range(5)])+';'
 def spec(self):return dict(codes=['000001','000002'],asOf='2025-01-05',start='2025-01-01',end='2025-01-05',conditions=[dict(kind='metric',field='maximumDrawdownPct',op='lt',value=20)],rank=dict(field='returnPct',direction='desc'))
 def test_real_alignment(self):
  rows,a=candidate_metrics({'000001':self.text('000001')},'2025-01-01','2025-01-05');self.assertEqual(a['observations'],5);self.assertAlmostEqual(rows[0]['fields']['returnPct']['value'],4)
 def test_failure_not_dropped_and_resume(self):
  with tempfile.TemporaryDirectory() as root:
   p=Path(root)/'out'
   def fetch(u):
    if '000002' in u:raise OSError('暂不可得')
    return self.text('000001')
   r=run(self.spec(),p,fetch=fetch);self.assertEqual(len(r['unknown']),1)
   calls=[]
   def retry(u):calls.append(u);return self.text('000002')
   r=run(self.spec(),p,True,fetch=retry);self.assertEqual(len(calls),1);self.assertEqual(len(r['selected']),2)
 def test_invalid_condition_does_not_collect(self):
  with tempfile.TemporaryDirectory() as root:
   spec=self.spec();spec['conditions'][0]['field']='invalid';calls=[]
   with self.assertRaises(ValueError):run(spec,Path(root)/'out',fetch=lambda u:calls.append(u))
   self.assertFalse(calls);self.assertFalse((Path(root)/'out').exists())
 def test_human_summary_missing_is_not_zero(self):
  with tempfile.TemporaryDirectory() as root:
   p=Path(root)/'out'
   def fetch(u):raise OSError('来源超时')
   run(self.spec(),p,fetch=fetch)
   text=(p/'筛选简报.md').read_text(encoding='utf-8');self.assertIn('资料不足2只',text);self.assertIn('未取得',text);self.assertIn('来源超时',text)
   self.assertTrue((p/'筛选简报.html').exists());self.assertIn('2025-01-01',text)
 def test_cache_tamper(self):
  with tempfile.TemporaryDirectory() as root:
   p=Path(root)/'out';run(self.spec(),p,fetch=lambda u:self.text(u.split('/')[-1][:6]));(p/'000001.js').write_text('changed',encoding='utf8')
   with self.assertRaises(ValueError):run(self.spec(),p,True,fetch=lambda u:'')
 def test_late_inception(self):
  rows,a=candidate_metrics({'000001':self.text('000001')},'2023-01-01','2025-01-05');self.assertFalse(rows);self.assertIn('000001',a['errors'])


 def test_invalid_rf_rejected_before_collection(self):
  with tempfile.TemporaryDirectory() as t:
   for value in [True,float('nan')]:
    s=self.spec();s['annualRiskFreePct']=value;calls=[]
    with self.assertRaises(ValueError):run(s,Path(t)/'out',fetch=lambda u:calls.append(u))
    self.assertEqual(calls,[]);self.assertFalse((Path(t)/'out').exists())
 def test_cache_hash_covers_exact_line_endings(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'out';run(self.spec(),p,fetch=lambda u:self.text(u.split('/')[-1][:6])+'\n')
   cache=p/'000001.js';raw=cache.read_bytes();self.assertTrue(raw.endswith(b'\n'));cache.write_bytes(raw[:-1]+b'\r\n')
   with self.assertRaisesRegex(ValueError,'哈希变化'):run(self.spec(),p,True,fetch=lambda u:'')

 def test_bad_metric_preserves_other_candidates(self):
  from unittest.mock import patch
  good={f'2025-01-0{i}':1+i*.01 for i in range(1,6)};bad=dict(good);bad['2025-01-03']=float('inf')
  with patch('fund_batch_screen.series',side_effect=[bad,good]):
   rows,alignment=candidate_metrics({'000001':self.text('000001'),'000002':self.text('000002')},'2025-01-01','2025-01-05')
  self.assertEqual([x['code'] for x in rows],['000002']);self.assertIn('指标计算未完成',alignment['errors']['000001'])
 def test_resume_preserves_previous_report_bytes(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'out'
   def initial(u):
    if '000002' in u:raise OSError('暂不可得')
    return self.text('000001')
   run(self.spec(),p,fetch=initial);before=(p/'result.json').read_bytes();brief=(p/'筛选简报.md').read_bytes()
   after=run(self.spec(),p,True,fetch=lambda u:self.text('000002'))
   state=json.loads((p/'collection.json').read_text('utf8'));record=state['previousOutputVersions'][0];version=p/record['path']
   self.assertEqual((version/'result.json').read_bytes(),before);self.assertEqual((version/'筛选简报.md').read_bytes(),brief);self.assertEqual(len(after['selected']),2);self.assertTrue((version/'manifest.json').is_file())
if __name__=='__main__':unittest.main()
