import unittest,copy
from research_workflow import compare_results,digest
class Tests(unittest.TestCase):
 def sample(self):
  result={'value':1,'identity':{'code':'600900'}};parameters={'asOf':'2026-10-05'};h=digest(parameters)
  return dict(type='research-template-result',template='example',contextHash=h,contextSnapshot=dict(parameters=parameters,contextHash=h),result=result,lineage=dict(files=[],calculations=[dict(outputSha256=digest(result),code=[dict(module='engine.py',sha256='a')])]))
 def test_code_change_blocks_direct_comparison(self):
  a=self.sample();b=copy.deepcopy(a);b['lineage']['calculations'][0]['code'][0]['sha256']='b'
  r=compare_results(a,b);self.assertFalse(r['directlyComparable']);self.assertEqual(r['codeChanges'],['engine.py'])
 def test_tampered_context_rejected(self):
  a=self.sample();b=copy.deepcopy(a);b['contextSnapshot']['parameters']['asOf']='2000-01-01'
  with self.assertRaisesRegex(ValueError,'上下文'):compare_results(a,b)
 def test_tampered_result_rejected(self):
  a=self.sample();b=copy.deepcopy(a);b['result']['value']=2
  with self.assertRaisesRegex(ValueError,'计算摘要'):compare_results(a,b)
 def test_changed_company_blocks_comparison(self):
  a=self.sample();b=copy.deepcopy(a);b['result']['identity']['code']='600031';b['lineage']['calculations'][0]['outputSha256']=digest(b['result'])
  r=compare_results(a,b);self.assertFalse(r['directlyComparable']);self.assertIn('研究对象不同',r['comparisonBlockers'])
 def test_event_assets_identified_and_comparator_change_blocks(self):
  a=self.sample();a['result']={'assetId':'QQQ','comparisonId':'TLT'};a['lineage']['calculations'][0]['outputSha256']=digest(a['result'])
  b=copy.deepcopy(a);r=compare_results(a,b)
  self.assertTrue(r['directlyComparable']);self.assertEqual(r['beforeSubjects'],['assetId:QQQ','comparisonId:TLT'])
  b['result']['comparisonId']='SPY';b['lineage']['calculations'][0]['outputSha256']=digest(b['result'])
  self.assertIn('研究对象不同',compare_results(a,b)['comparisonBlockers'])
 def test_macro_series_identity_uses_role_and_ignores_order(self):
  a=self.sample();a['template']='macro-observation-review';a['result']={'seriesContracts':[{'id':'DGS10','role':'macro'},{'id':'QQQ','role':'asset'}]};a['lineage']['calculations'][0]['outputSha256']=digest(a['result'])
  b=copy.deepcopy(a);b['result']['seriesContracts'].reverse();b['lineage']['calculations'][0]['outputSha256']=digest(b['result'])
  self.assertTrue(compare_results(a,b)['directlyComparable'])
  b['result']['seriesContracts'][0]['id']='TLT';b['lineage']['calculations'][0]['outputSha256']=digest(b['result'])
  self.assertIn('研究对象不同',compare_results(a,b)['comparisonBlockers'])
 def test_fof_root_is_identity_not_leaf_holdings(self):
  a=self.sample();a['template']='fof-lookthrough-review';a['result']={'rootFund':'006859','leaves':{'stock:X':0.1}};a['lineage']['calculations'][0]['outputSha256']=digest(a['result'])
  b=copy.deepcopy(a);b['result']['leaves']={'stock:Y':0.2};b['lineage']['calculations'][0]['outputSha256']=digest(b['result'])
  self.assertTrue(compare_results(a,b)['directlyComparable'])
  b['result']['rootFund']='OTHER';b['lineage']['calculations'][0]['outputSha256']=digest(b['result']);self.assertIn('研究对象不同',compare_results(a,b)['comparisonBlockers'])
 def test_generic_ids_do_not_establish_macro_identity(self):
  a=self.sample();a['result']={'id':'QQQ'};a['lineage']['calculations'][0]['outputSha256']=digest(a['result']);self.assertFalse(compare_results(a,a)['directlyComparable'])
 def test_company_conventions_change_blocks_and_missing_is_change(self):
  a=self.sample();a['result']={'companies':[{'code':'600900','metadata':{'unit':'元','scope':'consolidated','classificationVersion':'v1'}}]};a['lineage']['calculations'][0]['outputSha256']=digest(a['result'])
  self.assertTrue(compare_results(a,a)['directlyComparable'])
  for field in ['unit','scope','classificationVersion']:
   b=copy.deepcopy(a);b['result']['companies'][0]['metadata'][field]='changed';b['lineage']['calculations'][0]['outputSha256']=digest(b['result']);r=compare_results(a,b)
   self.assertFalse(r['directlyComparable']);self.assertEqual(r['conventionChanges'][0]['field'],field)
  b=copy.deepcopy(a);del b['result']['companies'][0]['metadata']['unit'];b['lineage']['calculations'][0]['outputSha256']=digest(b['result']);self.assertFalse(compare_results(a,b)['directlyComparable'])
 def test_company_order_not_convention_change(self):
  a=self.sample();a['result']={'companies':[{'code':'A','metadata':{'unit':'元'}},{'code':'B','metadata':{'unit':'万元'}}]};a['lineage']['calculations'][0]['outputSha256']=digest(a['result']);b=copy.deepcopy(a);b['result']['companies'].reverse();b['lineage']['calculations'][0]['outputSha256']=digest(b['result']);self.assertTrue(compare_results(a,b)['directlyComparable'])
 def convention_pair(self,old,new):
  a=self.sample();a['result']={'companies':[{'code':'600900','metadata':old}]};a['lineage']['calculations'][0]['outputSha256']=digest(a['result'])
  b=copy.deepcopy(a);b['result']['companies'][0]['metadata']=new;b['lineage']['calculations'][0]['outputSha256']=digest(b['result']);return compare_results(a,b)
 def test_added_record_is_not_actual_change(self):
  from research_workflow import version_comparison_markdown
  r=self.convention_pair({},dict(unit='元'));self.assertEqual(r['conventionChanges'][0]['changeType'],'record-added');self.assertFalse(r['directlyComparable']);self.assertIn('不能据此认定实际口径改变',version_comparison_markdown(r))
 def test_removed_record_is_unknown(self):
  from research_workflow import version_comparison_markdown
  r=self.convention_pair(dict(scope='consolidated'),{});self.assertEqual(r['conventionChanges'][0]['changeType'],'record-missing');self.assertIn('新版缺少记录',version_comparison_markdown(r))
 def test_two_known_values_change(self):
  r=self.convention_pair(dict(unit='元'),dict(unit='万元'));self.assertEqual(r['conventionChanges'][0]['changeType'],'value-changed');self.assertFalse(r['directlyComparable'])
 def test_empty_record_not_treated_as_known(self):
  r=self.convention_pair(dict(unit=''),dict(unit='元'));self.assertEqual(r['conventionChanges'][0]['changeType'],'record-added')
 def financial_pair(self,meta):
  a=self.sample();a['template']='company-financial-review';a['result']={'companies':[{'code':'600900','metadata':meta}]};a['lineage']['calculations'][0]['outputSha256']=digest(a['result']);return compare_results(a,copy.deepcopy(a))
 def test_both_missing_financial_conventions_block(self):
  r=self.financial_pair({});self.assertFalse(r['directlyComparable']);self.assertEqual(len(r['conventionGaps']),10);self.assertEqual(r['conventionChanges'],[])
 def test_complete_financial_conventions_allow_comparison(self):
  r=self.financial_pair(dict(unit='元',scope='consolidated',currency='CNY',classificationVersion='v1',sectorType='industrial'));self.assertTrue(r['directlyComparable']);self.assertEqual(r['conventionGaps'],[])
 def test_blank_financial_convention_blocks(self):
  r=self.financial_pair(dict(unit='  ',scope='consolidated',currency='CNY',classificationVersion='v1',sectorType='industrial'));self.assertEqual([x['field'] for x in r['conventionGaps']],['unit','unit'])
 def test_human_report_no_module_names(self):
  from research_workflow import version_comparison_markdown
  a=self.sample();b=copy.deepcopy(a);b['lineage']['calculations'][0]['code'][0]['sha256']='changed'
  text=version_comparison_markdown(compare_results(a,b));self.assertIn('不能直接比较',text);self.assertNotIn('engine.py',text)
 def test_missing_calculation_or_digest_rejected(self):
  a=self.sample();b=copy.deepcopy(a);b['lineage']['calculations']=[]
  with self.assertRaisesRegex(ValueError,'计算记录'):compare_results(a,b)
  b=copy.deepcopy(a);del b['lineage']['calculations'][0]['outputSha256']
  with self.assertRaisesRegex(ValueError,'计算摘要'):compare_results(a,b)
 def test_conflicting_method_and_source_versions_rejected(self):
  a=self.sample();b=copy.deepcopy(a);b['lineage']['calculations'][0]['code'].append(dict(module='engine.py',sha256='conflict'))
  with self.assertRaisesRegex(ValueError,'冲突版本'):compare_results(a,b)
  b=copy.deepcopy(a);b['lineage']['files']=[dict(role='original',path='a.pdf',sha256='one'),dict(role='original',path='a.pdf',sha256='two')]
  with self.assertRaisesRegex(ValueError,'冲突版本'):compare_results(a,b)
if __name__=='__main__':unittest.main()
