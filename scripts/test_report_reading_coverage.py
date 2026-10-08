import unittest,copy
from report_reading_coverage import review_coverage
class Tests(unittest.TestCase):
 def sample(self):
  r=dict(sha256='x',pages=[dict(page=1,text='图表34：不同回看天数下综合因子\n回看20日 回看40日 回看60日\n年化收益率 24.68% 20.58% 18.66%\n一、前言与模型研究')])
  a=dict(numericTableChecks=[dict(page=1,tableTitle='图表34：不同回看天数下综合因子',columns=['回看20日','回看40日','回看60日'],headingQuote='回看20日 回看40日 回看60日',rowLabel='年化收益率',rowQuote='年化收益率 24.68% 20.58% 18.66%',values=[24.68,20.58,18.66],unit='percent')]);return a,r
 def test_duplicate_pages_not_overwritten(self):
  a,r=self.sample();r['pages'].append(dict(r['pages'][0]))
  with self.assertRaisesRegex(ValueError,'物理页重复'):review_coverage(a,r)
 def test_missing_middle_page_blocks_range(self):
  a,r=self.sample();r['pages'].append(dict(page=3,text='第三页'));a['sectionReviews']=[dict(title='前言',startPage=1,endPage=3,status='reviewed',note='已读',evidence=[dict(page=1,quote='一、前言与模型研究')])]
  with self.assertRaisesRegex(ValueError,'缺少物理页'):review_coverage(a,r)
 def test_empty_page_remains_gap(self):
  a,r=self.sample();r['pages'].append(dict(page=2,text=''));a['sectionReviews']=[dict(title='前言',startPage=1,endPage=2,status='reviewed',note='已读',evidence=[dict(page=1,quote='一、前言与模型研究')])]
  self.assertIn('无可解析文本页',review_coverage(a,r)['gaps'][0])
 def test_repeated_table_title_rejected(self):
  a,r=self.sample();r['pages'][0]['text']+='\n'+r['pages'][0]['text']
  with self.assertRaisesRegex(ValueError,'标题重复'):review_coverage(a,r)
 def test_values_verified_no_backtest_claim(self):
  a,r=self.sample();v=review_coverage(a,r)['numericTables'][0];self.assertEqual(v['values'],['24.68','20.58','18.66']);self.assertIn('未重算回测',v['limitations'])
 def test_swapped_values_and_columns_rejected(self):
  for key,value in [('values',[20.58,24.68,18.66]),('columns',['回看40日','回看20日','回看60日']),('unit','number'),('page',True)]:
   a,r=self.sample();a['numericTableChecks'][0][key]=value
   with self.assertRaises(ValueError):review_coverage(a,r)
 def test_reading_status_is_declared_and_pending_gap(self):
  a,r=self.sample();a['sectionReviews']=[dict(title='前言',startPage=1,endPage=1,status='pending',note='尚待阅读全文',evidence=[dict(page=1,quote='一、前言与模型研究')])]
  v=review_coverage(a,r);self.assertEqual(len(v['gaps']),1);self.assertIn('user-declared',v['sections'][0]['verificationScope'])
 def test_invalid_ranges_and_duplicate_titles(self):
  a,r=self.sample();s=dict(title='前言',startPage=1,endPage=1,status='reviewed',note='阅读记录',evidence=[dict(page=1,quote='一、前言与模型研究')]);a['sectionReviews']=[s,s]
  with self.assertRaises(ValueError):review_coverage(a,r)
 def test_missing_quote_rejected(self):
  a,r=self.sample();a['numericTableChecks'][0]['rowQuote']='年化收益率 99.00% 20.58% 18.66%'
  with self.assertRaises(ValueError):review_coverage(a,r)
 def test_same_page_other_table_cannot_supply_values(self):
  a,r=self.sample();r['pages'][0]['text']='图表34：不同回看天数下综合因子\n回看20日 回看40日 回看60日\n图表35：其他样本空间测试\n年化收益率 24.68% 20.58% 18.66%'
  with self.assertRaisesRegex(ValueError,'同一标题'):review_coverage(a,r)

class GroupedTableTests(unittest.TestCase):
 def sample(self):
  report=dict(sha256='x',pages=[dict(page=1,text='图表20：信号叠加前后收益表现\n通道策略绝对收益 通道策略相比800等权超额\n低位放量 叠加信号 低位放量 叠加信号\n最大回撤 32.92% 32.49% 4.68% 3.70%')])
  row=dict(page=1,tableTitle='图表20：信号叠加前后收益表现',columns=['低位放量','叠加信号','低位放量','叠加信号'],columnGroups=['通道策略绝对收益']*2+['通道策略相比800等权超额']*2,groupHeadingQuote='通道策略绝对收益 通道策略相比800等权超额',headingQuote='低位放量 叠加信号 低位放量 叠加信号',rowLabel='最大回撤',rowQuote='最大回撤 32.92% 32.49% 4.68% 3.70%',values=[32.92,32.49,4.68,3.70],unit='percent')
  return dict(numericTableChecks=[row]),report
 def test_absolute_and_excess_columns_preserved(self):
  a,r=self.sample();x=review_coverage(a,r)['numericTables'][0];self.assertEqual(x['values'],['32.92','32.49','4.68','3.7']);self.assertIn('not-coordinate-verified',x['groupMappingStatus'])
 def test_missing_reversed_and_interleaved_groups_rejected(self):
  for mode in ['missing','reversed','interleaved']:
   a,r=self.sample();row=a['numericTableChecks'][0]
   if mode=='missing':row.pop('columnGroups')
   elif mode=='reversed':row['columnGroups']=row['columnGroups'][::-1]
   else:row['columnGroups']=[row['columnGroups'][i] for i in [0,2,1,3]]
   with self.assertRaises(ValueError):review_coverage(a,r)

if __name__=='__main__':unittest.main()
