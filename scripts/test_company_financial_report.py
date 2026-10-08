import unittest
from company_financial_report import original_checks,checked_interpretation,comparative_header_confirmed,original_check_description
class Tests(unittest.TestCase):
 def test_signed_expense_presentation_needs_independent_context(self):
  a,r=self.inputs();a['tables']['income']['rows'][0]['raw']['OPERATE_COST']=60
  r['pages'][0]['text']='合并利润表\n单位：元 币种：人民币\n项目 附注 2026年半年度 2025年半年度\n营业收入 100.00 90.00\n其中：营业成本 七、61 -60.00 -50.00\n二、营业总成本 -70.00 -60.00\n销售费用 -5.00 -4.00\n管理费用 -5.00 -6.00\n母公司利润表'
  cost=next(x for x in original_checks(a,r,'2026-06-30') if x['metric']=='cost')
  self.assertEqual(cost['status'],'matched');self.assertEqual(cost['original'][0]['reportedValue'],'-60.00');self.assertEqual(cost['original'][0]['signBasis'],'expense-magnitude-from-signed-expense-presentation')
  r['pages'][0]['text']=r['pages'][0]['text'].replace('管理费用 -5.00 -6.00','管理费用 5.00 6.00')
  self.assertEqual(next(x for x in original_checks(a,r,'2026-06-30') if x['metric']=='cost')['status'],'difference')
 def test_appraisal_title_is_preserved_but_markup_rejected(self):
  report=dict(fileSha256='hash',pages=[dict(page=1,text='汽车玻璃收入增长，但库存周转延长。')])
  entry=dict(text='收入改善仍需检验库存消化。',title='经营质量评价',basis='research-explanation',evidence=[dict(page=1,quote='汽车玻璃收入增长')],followUp=['核对库存库龄'])
  self.assertEqual(checked_interpretation(entry,report)['title'],'经营质量评价')
  for invalid in ['#伪标题','多行\n标题',123,'']:
   with self.assertRaises(ValueError):checked_interpretation(dict(entry,title=invalid),report)
 def test_numeric_parenthesized_note_is_not_an_amount(self):
  a,r=self.inputs();a['tables']['cashflow']['rows'][0]['raw']['NETCASH_OPERATE']=30
  a['tables']['cashflow']['rows'].append(dict(period='2025-06-30',publishedAt='2025-08-22',currency='CNY',raw=dict(NETCASH_OPERATE=25)))
  r['pages'][0]['text']='合并现金流量表\n单位：元 币种：人民币\n项目 附注七 2026年半年度 2025年半年度\n经营活动产生的现金流量净额 79(1) 30.00 25.00\n母公司现金流量表'
  for column in ['current','comparative']:
   c=next(x for x in original_checks(a,r,'2026-06-30',column) if x['metric']=='operatingCash');self.assertEqual(c['status'],'matched')
  r['pages'][0]['text']=r['pages'][0]['text'].replace('30.00 25.00','30.00 25.00 24.00')
  self.assertEqual(next(x for x in original_checks(a,r,'2026-06-30') if x['metric']=='operatingCash')['status'],'column-ambiguous')
 def test_amount_wrapped_to_next_line_requires_header_and_same_page(self):
  a,r=self.inputs();a['tables']['income']['rows'].append(dict(period='2025-06-30',publishedAt='2025-08-22',currency='CNY',raw=dict(OPERATE_INCOME=90)))
  r['pages'][0]['text']=r['pages'][0]['text'].replace('100.00 90.00','100.00\n90.00')
  for column in ['current','comparative']:self.assertEqual(original_checks(a,r,'2026-06-30',column)[0]['status'],'matched')
  r['pages'][0]['text']=r['pages'][0]['text'].replace('2025年半年度','未知期间')
  self.assertNotEqual(original_checks(a,r,'2026-06-30')[0]['status'],'matched')
  a,r=self.inputs();r['pages'][0]['text']=r['pages'][0]['text'].replace('100.00 90.00','100.00\n其他收入 90.00')
  self.assertNotEqual(original_checks(a,r,'2026-06-30')[0]['status'],'matched')
 def test_wrapped_label_after_amounts_preserves_ownership_and_cash(self):
  a,r=self.inputs();a['tables']['income']['rows'][0]['raw']['PARENT_NETPROFIT']=19
  a['tables']['cashflow']['rows'][0]['raw']['NETCASH_OPERATE']=30
  r['pages'][0]['text']+='\n合并利润表\n单位：元\n1.归属于母公司股东的 19.00 17.00\n净利润（净亏损以亏损号\n填列）\n母公司利润表\n合并现金流量表\n单位：元\n经营活动产生的现 30.00 25.00\n金流量净额\n母公司现金流量表'
  by={x['metric']:x for x in original_checks(a,r,'2026-06-30')}
  self.assertEqual(by['parentProfit']['status'],'matched');self.assertEqual(by['operatingCash']['status'],'matched')
 def test_wrapped_label_does_not_cross_page(self):
  a,r=self.inputs();a['tables']['cashflow']['rows'][0]['raw']['NETCASH_OPERATE']=30
  r['pages']=[dict(page=1,text='合并现金流量表\n单位：元\n经营活动产生的现 30.00 25.00'),dict(page=2,text='金流量净额\n母公司现金流量表')]
  self.assertNotEqual(next(x for x in original_checks(a,r,'2026-06-30') if x['metric']=='operatingCash')['status'],'matched')
 def test_chinese_parenthesized_note_with_confirmed_note_column(self):
  a,r=self.inputs();a['tables']['income']['rows'][0]['raw']['OPERATE_COST']=60
  r['pages'][0]['text']='合并利润表\n单位：元 币种：人民币\n项目 附注 2026年半年度 2025年半年度\n其中：营业收入 七（61） 100.00 90.00\n其中：营业成本 七（61） 60.00 50.00\n母公司利润表'
  by={c['metric']:c for c in original_checks(a,r,'2026-06-30')};self.assertEqual(by['revenue']['status'],'matched');self.assertEqual(by['cost']['status'],'matched')
  r['pages'][0]['text']=r['pages'][0]['text'].replace('项目 附注','项目')
  self.assertEqual(original_checks(a,r,'2026-06-30')[0]['status'],'missing')
 def test_chinese_comma_parenthesized_note(self):
  a,r=self.inputs();r['pages'][0]['text']='合并利润表\n单位：元 币种：人民币\n项目 附注 2026年半年度 2025年半年度\n其中：营业收入 七、（61） 100.00 90.00\n母公司利润表'
  self.assertEqual(original_checks(a,r,'2026-06-30')[0]['status'],'matched')
  r['pages'][0]['text']=r['pages'][0]['text'].replace('项目 附注','项目')
  self.assertNotEqual(original_checks(a,r,'2026-06-30')[0]['status'],'matched')
 def test_wrapped_ownership_label_is_not_total_profit(self):
  a,r=self.inputs();a['tables']['income']['rows'][0]['raw']['PARENT_NETPROFIT']=19
  r['pages'][0]['text']=r['pages'][0]['text'].replace('4、母公司利润表','1.归属于母公司股东的\n净利润（净亏损以亏损号填 19.00 17.00\n列）\n4、母公司利润表')
  by={x['metric']:x for x in original_checks(a,r,'2026-06-30')}
  self.assertEqual(by['profit']['status'],'matched');self.assertEqual(by['parentProfit']['status'],'matched')
  r['pages'][0]['text']=r['pages'][0]['text'].replace('1.归属于母公司股东的\n','')
  by={x['metric']:x for x in original_checks(a,r,'2026-06-30')}
  self.assertEqual(by['profit']['status'],'ambiguous');self.assertEqual(by['parentProfit']['status'],'missing')
 def test_nested_note_does_not_become_numeric_column(self):
  a=dict(code='600309',asOf='2026-10-05',tables={k:dict(rows=[dict(period='2025-06-30',publishedAt='2025-08-12',currency='CNY',raw=dict(NETCASH_OPERATE=100))]) for k in ['income','balance','cashflow']})
  r=dict(code='600309',period='2025-06-30',asOf='2026-10-05',parseStatus='parsed',pages=[dict(page=41,text='合并现金流量表\n单位：元 币种：人民币\n项目 附注 2025年半年度 2024年半年度\n经营活动产生的现金流量净额 七79（1） 100.00 90.00\n母公司现金流量表')])
  c=next(c for c in original_checks(a,r,'2025-06-30') if c['metric']=='operatingCash');self.assertEqual(c['status'],'matched');self.assertEqual(c['original'][0]['reportedValue'],'100.00')
 def inputs(self):
  a=dict(code='300308',asOf='2026-10-05',tables={k:dict(rows=[dict(period='2026-06-30',publishedAt='2026-08-22',currency='CNY',raw=dict(OPERATE_INCOME=100,NETPROFIT=20))]) for k in ['income','balance','cashflow']})
  r=dict(code='300308',period='2026-06-30',asOf='2026-10-05',parseStatus='parsed',pages=[dict(page=1,text='3、合并利润表\n单位：元\n项目 2026年半年度 2025年半年度\n其中：营业收入 100.00 90.00\n五、净利润（净亏损以亏损号填\n20.00 18.00\n列）\n4、母公司利润表\n营业收入 300.00 250.00')]);return a,r
 def test_wrapped_and_parent_exclusion(self):
  a,r=self.inputs();checks=original_checks(a,r,'2026-06-30');by={x['metric']:x for x in checks};self.assertEqual(by['revenue']['status'],'matched');self.assertEqual(by['profit']['status'],'matched')
 def test_difference_and_ambiguity(self):
  a,r=self.inputs();r['pages'][0]['text']=r['pages'][0]['text'].replace('100.00 90.00','101.00 90.00');self.assertEqual(original_checks(a,r,'2026-06-30')[0]['status'],'difference')
  a,r=self.inputs();r['pages'][0]['text']=r['pages'][0]['text'].replace('4、母公司利润表','营业收入 100.00 90.00\n4、母公司利润表');self.assertEqual(original_checks(a,r,'2026-06-30')[0]['status'],'ambiguous')
 def test_identity(self):
  a,r=self.inputs();r['code']='002475'
  with self.assertRaises(ValueError):original_checks(a,r,'2026-06-30')
 def test_unnumbered_heading_and_note_column(self):
  a,r=self.inputs();r['pages'][0]['text']=r['pages'][0]['text'].replace('3、合并利润表','合并利润表').replace('4、母公司利润表','母公司利润表').replace('单位：元','单位： 元 币种：人民币').replace('营业收入 100.00','营业收入 七61 100.00');self.assertEqual(original_checks(a,r,'2026-06-30')[0]['status'],'matched')
 def test_bare_integer_note_requires_header_and_three_columns(self):
  a,r=self.inputs();r['pages'][0]['text']=r['pages'][0]['text'].replace('项目 2026','项目 附注 2026').replace('营业收入 100.00 90.00','营业收入 43 100.00 90.00')
  check=original_checks(a,r,'2026-06-30')[0];self.assertEqual(check['status'],'matched');self.assertEqual(check['original'][0]['reportedValue'],'100.00')
  r['pages'][0]['text']=r['pages'][0]['text'].replace('营业收入 43 100.00 90.00','营业收入 100 90')
  self.assertEqual(original_checks(a,r,'2026-06-30')[0]['status'],'matched')
 def test_wanyuan_scaled_not_silently_compared(self):
  a,r=self.inputs();r['pages'][0]['text']=r['pages'][0]['text'].replace('单位：元','单位：万元');check=original_checks(a,r,'2026-06-30')[0];self.assertEqual(check['status'],'difference');self.assertEqual(check['original'][0]['convertedValueCNY'],'1000000.00')
 def test_integer_thousand_and_note_column(self):
  a,r=self.inputs();a['tables']['income']['rows'][0]['raw']['OPERATE_INCOME']=100000;r['pages'][0]['text']=r['pages'][0]['text'].replace('单位：元','单位：千元').replace('营业收入 100.00 90.00','营业收入 七、54 100 90');check=original_checks(a,r,'2026-06-30')[0];self.assertEqual(check['status'],'matched');self.assertEqual(check['original'][0]['roundingToleranceCNY'],'500')
 def test_unknown_unit_retained(self):
  a,r=self.inputs();r['pages'][0]['text']=r['pages'][0]['text'].replace('单位：元','单位：百万美元');self.assertEqual(original_checks(a,r,'2026-06-30')[0]['status'],'unit-unconfirmed')
 def test_unit_conflict_not_chosen(self):
  a,r=self.inputs();r['pages'][0]['text']=r['pages'][0]['text'].replace('单位：元','单位：元\n单位：千元');self.assertEqual(original_checks(a,r,'2026-06-30')[0]['status'],'unit-unconfirmed')
 def test_currency_adjacent_audit_label(self):
  a,r=self.inputs();r['pages'][0]['text']=r['pages'][0]['text'].replace('单位：元','单位：元币种:人民币审计类型：未经审计')
  self.assertEqual(original_checks(a,r,'2026-06-30')[0]['status'],'matched')
 def test_adjacent_unknown_currency_not_truncated(self):
  a,r=self.inputs();r['pages'][0]['text']=r['pages'][0]['text'].replace('单位：元','单位：元币种:人民币美元审计类型：未经审计')
  self.assertEqual(original_checks(a,r,'2026-06-30')[0]['status'],'unit-unconfirmed')
 def test_foreign_currency_not_scaled_to_cny(self):
  a,r=self.inputs();r['pages'][0]['text']=r['pages'][0]['text'].replace('单位：元','单位：千元 币种：美元');self.assertEqual(original_checks(a,r,'2026-06-30')[0]['status'],'unit-unconfirmed')
 def test_follow_up_is_question_not_evidence(self):
  report=dict(fileSha256='abc',pages=[dict(page=1,text='报告期内公司核心竞争力保持稳健。')])
  entry=dict(text='公司称竞争力保持稳健。',basis='company-statement',evidence=[dict(page=1,quote='报告期内公司核心竞争力保持稳健。')],followUp=['  是否有可比数据支持？  '])
  checked=checked_interpretation(entry,report)
  self.assertEqual(checked['followUp'],['是否有可比数据支持？'])
  self.assertEqual(len(checked['evidence']),1)
  for invalid in ['问题',[None],[' ']]:
   with self.assertRaises(ValueError):checked_interpretation(dict(entry,followUp=invalid),report)
 def test_parent_profit_label_split_around_numeric_row(self):
  a,r=self.inputs();a['tables']['income']['rows'][0]['raw']['PARENT_NETPROFIT']=19
  r['pages'][0]['text']=r['pages'][0]['text'].replace('4、母公司利润表','1.归属于母公司股东的净利\n19.00 17.00\n润（净亏损以“-”号填列）\n4、母公司利润表')
  check=next(x for x in original_checks(a,r,'2026-06-30') if x['metric']=='parentProfit')
  self.assertEqual(check['status'],'matched');self.assertIn('净利润',check['original'][0]['label'])
 def test_parallel_current_consolidated_and_expense_sign(self):
  a,r=self.inputs();a['tables']['income']['rows'][0]['raw'].update(OPERATE_INCOME=100000,OPERATE_COST=50000)
  r['pages'][0]['text']='2026年半年度合并及公司利润表\n(除特别注明外，金额单位为人民币千元)\n2026年半年度 2025年半年度 2026年半年度 2025年半年度\n项 目 附注\n合并 合并 公司 公司\n其中：营业收入 四(46),十七(3) 100 90 999 888\n其中：营业成本 四(46) (50) (40) (900) (800)'
  checks={x['metric']:x for x in original_checks(a,r,'2026-06-30')};self.assertEqual(checks['revenue']['status'],'matched');self.assertEqual(checks['cost']['status'],'matched');self.assertEqual(checks['cost']['original'][0]['reportedValue'],'-50')
  r['pages'][0]['text']=r['pages'][0]['text'].replace('合并 合并 公司 公司','公司 公司 合并 合并')
  self.assertNotEqual(original_checks(a,r,'2026-06-30')[0]['status'],'matched')
 def test_comparative_period_and_explicit_header(self):
  a,r=self.inputs();a['tables']['income']['rows'].append(dict(period='2025-06-30',publishedAt='2025-08-22',currency='CNY',raw=dict(OPERATE_INCOME=90,NETPROFIT=18)))
  by={x['metric']:x for x in original_checks(a,r,'2026-06-30',column='comparative')}
  self.assertEqual(by['revenue']['status'],'matched');self.assertEqual(by['revenue']['observationPeriod'],'2025-06-30');self.assertEqual(by['assets']['observationPeriod'],'2025-12-31')
  r['pages'][0]['text']=r['pages'][0]['text'].replace('2025年半年度','上期')
  self.assertEqual(original_checks(a,r,'2026-06-30',column='comparative')[0]['status'],'period-unconfirmed')
 def test_comparative_headers_order_and_quarter(self):
  self.assertTrue(comparative_header_confirmed([(1,'项目 2026年1—9月 2025年1—9月')],'income','2026-09-30'))
  self.assertFalse(comparative_header_confirmed([(1,'项目 2025年半年度 2026年半年度')],'income','2026-06-30'))
  self.assertFalse(comparative_header_confirmed([(1,'项目 2026年9月30日 2025年9月30日')],'balance','2026-09-30'))
  self.assertTrue(comparative_header_confirmed([(1,'项目 2026年9月30日 2025年12月31日')],'balance','2026-09-30'))
  self.assertFalse(comparative_header_confirmed([(1,'2026年 2025年 2026年 2025年'),(1,'6月30日 6月30日 6月30日 6月30日')],'balance','2026-06-30',True))
 def test_extra_comparative_columns_not_silently_selected(self):
  a,r=self.inputs();a['tables']['income']['rows'].append(dict(period='2025-06-30',publishedAt='2025-08-22',currency='CNY',raw=dict(OPERATE_INCOME=90)))
  r['pages'][0]['text']=r['pages'][0]['text'].replace('100.00 90.00','100.00 90.00 80.00')
  x=original_checks(a,r,'2026-06-30',column='comparative')[0]
  self.assertEqual(x['status'],'column-ambiguous');self.assertEqual(x['original'],[]);self.assertTrue(x['columnConflicts'])
 def test_invalid_column(self):
  a,r=self.inputs()
  with self.assertRaises(ValueError):original_checks(a,r,'2026-06-30',column='other')
 def test_bank_million_and_ownership_columns(self):
  a,r=self.inputs()
  a['tables']['income']['rows'][0]['raw'].update(OPERATE_INCOME=100000000,PARENT_NETPROFIT=19000000)
  a['tables']['income']['rows'].append(dict(period='2025-06-30',publishedAt='2025-08-22',currency='CNY',raw=dict(OPERATE_INCOME=90000000,PARENT_NETPROFIT=17000000)))
  r['pages'][0]['text']='合并及公司利润表\n（除特别注明外，金额单位均为人民币百万元）\n本集团 本行\n截至6月30日止六个月 截至6月30日止六个月\n2026年 2025年 2026年 2025年\n营业收入 100 90 999 888\n净利润归属于：\n母公司股东 19 17'
  for col in ['current','comparative']:
   checks={x['metric']:x for x in original_checks(a,r,'2026-06-30',col)}
   self.assertEqual(checks['revenue']['status'],'matched');self.assertEqual(checks['parentProfit']['status'],'matched')
   self.assertEqual(checks['revenue']['original'][0]['reportedUnit'],'百万元')
  r['pages'][0]['text']=r['pages'][0]['text'].replace('本集团 本行','本行 本集团')
  self.assertNotEqual(original_checks(a,r,'2026-06-30')[0]['status'],'matched')
 def test_bank_wrapped_cashflow_and_unknown_currency(self):
  a,r=self.inputs();a['tables']['cashflow']['rows'][0]['raw']['NETCASH_OPERATE']=100000000
  r['pages'][0]['text']='合并及公司现金流量表\n（金额单位均为人民币百万元）\n本集团 本行\n截至6月30日止六个月\n2026年 2025年 2026年 2025年\n经营活动产生的现金流量净额\n（附注四、44） 100 90 999 888'
  check=next(x for x in original_checks(a,r,'2026-06-30') if x['metric']=='operatingCash')
  self.assertEqual(check['status'],'matched');self.assertEqual(check['original'][0]['reportedValue'],'100')
  r['pages'][0]['text']=r['pages'][0]['text'].replace('人民币百万元','美元百万元')
  check=next(x for x in original_checks(a,r,'2026-06-30') if x['metric']=='operatingCash')
  self.assertEqual(check['status'],'unit-unconfirmed')
class ParallelGuardTests(unittest.TestCase):
 inputs=Tests.inputs
 def test_parallel_current_rejects_incomplete_or_extra_columns(self):
  for numbers in ['100 90 999','43 100 90 999 888']:
   a,r=self.inputs();a['tables']['income']['rows'][0]['raw']['OPERATE_INCOME']=100000000
   r['pages'][0]['text']='合并及公司利润表\n（金额单位均为人民币百万元）\n本集团 本行\n截至6月30日止六个月\n2026年 2025年 2026年 2025年\n营业收入 '+numbers
   c=original_checks(a,r,'2026-06-30')[0]
   self.assertEqual(c['status'],'column-ambiguous');self.assertEqual(c['original'],[])
 def test_parallel_current_does_not_infer_wrong_interval(self):
  a,r=self.inputs();r['pages'][0]['text']='合并及公司利润表\n（金额单位均为人民币百万元）\n本集团 本行\n截至9月30日止九个月\n2026年 2025年 2026年 2025年\n营业收入 100 90 999 888'
  self.assertEqual(original_checks(a,r,'2026-06-30')[0]['status'],'period-unconfirmed')
class CheckDescriptionTests(unittest.TestCase):
 def test_every_emitted_status_has_human_explanation(self):
  for status in ['matched','difference','missing','source-missing','period-unconfirmed','column-ambiguous','unit-unconfirmed','ambiguous']:
   for column in ['current','comparative']:
    text=original_check_description(dict(status=status,column=column,difference=None))
    self.assertTrue(text);self.assertNotIn(status,text)
 def test_difference_sign_and_unknown_status(self):
  text=original_check_description(dict(status='difference',column='current',difference='-100'))
  self.assertIn('-100元',text);self.assertIn('数据源减原文',text)
  with self.assertRaises(ValueError):original_check_description(dict(status='invented'))
class UnauditedBankLayoutTests(unittest.TestCase):
 def test_unit_total_label_and_company_table_exclusion(self):
  a,r=Tests().inputs();a['tables']['income']['rows'][0]['raw']['OPERATE_INCOME']=100000000
  r['pages'][0]['text']='未经审计合并利润表\n（货币单位均以人民币百万元列示）\n项目 附注 2026年 2025年\n营业收入合计 100 90\n未经审计公司利润表\n营业收入合计 999 888'
  c=original_checks(a,r,'2026-06-30')[0]
  self.assertEqual(c['status'],'matched');self.assertEqual(len(c['original']),1)
 def test_alphabetic_note_not_cashflow_value(self):
  a,r=Tests().inputs();a['tables']['cashflow']['rows'][0]['raw']['NETCASH_OPERATE']=100000000
  r['pages'][0]['text']='未经审计合并现金流量表\n（货币单位均以人民币百万元列示）\n项目 附注 2026年 2025年\n经营活动产生的现金流量净额 50(a) 100 90\n未经审计公司现金流量表'
  c=next(c for c in original_checks(a,r,'2026-06-30') if c['metric']=='operatingCash')
  self.assertEqual(c['status'],'matched');self.assertEqual(c['original'][0]['reportedValue'],'100')
class SplitBankHeaderTests(unittest.TestCase):
 def test_two_column_header_periods(self):
  self.assertTrue(comparative_header_confirmed([(1,'2026年 2025年'),(1,'项目 附注 6月30日 12月31日')],'balance','2026-06-30'))
  self.assertFalse(comparative_header_confirmed([(1,'2026年 2025年'),(1,'项目 附注 6月30日 6月30日')],'balance','2026-06-30'))
  self.assertTrue(comparative_header_confirmed([(1,'截至6月30日止6个月期间'),(1,'项目 附注 2026年 2025年')],'income','2026-06-30'))
 def test_repeated_bank_profit_retains_both_pages(self):
  a,r=Tests().inputs();a['tables']['income']['rows'][0]['raw'].update(ORG_TYPE='银行',NETPROFIT=20000000)
  r['pages']=[dict(page=1,text='未经审计合并利润表\n（货币单位均以人民币百万元列示）\n净利润 20 18'),dict(page=2,text='净利润 20 18\n未经审计公司利润表')]
  c=next(c for c in original_checks(a,r,'2026-06-30') if c['metric']=='profit')
  self.assertEqual(c['status'],'matched');self.assertTrue(c['repeatedConsistentDisclosure']);self.assertEqual([x['page'] for x in c['original']],[1,2])
  r['pages'][1]['text']=r['pages'][1]['text'].replace('20 18','21 18')
  c=next(c for c in original_checks(a,r,'2026-06-30') if c['metric']=='profit')
  self.assertEqual(c['status'],'ambiguous');self.assertFalse(c['repeatedConsistentDisclosure'])
class UnqualifiedCompanyStatementTests(unittest.TestCase):
 def test_unqualified_unaudited_table_ends_consolidated_section(self):
  a,r=Tests().inputs();a['tables']['income']['rows'][0]['raw'].update(ORG_TYPE='银行',OPERATE_INCOME=100000000)
  r['pages'][0]['text']='未经审计合并利润表\n（货币单位均以人民币百万元列示）\n营业收入合计 100 90\n未经审计利润表\n营业收入合计 999 888'
  c=original_checks(a,r,'2026-06-30')[0]
  self.assertEqual(c['status'],'matched');self.assertEqual(len(c['original']),1)
class UnavailableOriginalTests(unittest.TestCase):
 def test_absent_original_is_explicitly_unavailable(self):
  rows=original_checks({},None,'2026-06-30');self.assertEqual(len(rows),14);self.assertTrue(all(r['status']=='original-unavailable' for r in rows));self.assertIn('没有该公司',rows[0]['reason'])
 def test_unparsed_original_is_not_empty_pass(self):
  rows=original_checks({},dict(parseStatus='failed',error='download response not PDF'),'2026-06-30')
  self.assertEqual(len(rows),14);self.assertTrue(all(r['status']=='original-unavailable' for r in rows));self.assertFalse(all(r['status']=='matched' for r in rows));self.assertTrue(all(r['original']==[] for r in rows))
 def test_unparsed_comparative_keeps_scope(self):
  rows=original_checks({},dict(parseStatus='not-attempted'),'2026-06-30',column='comparative')
  self.assertTrue(all(r['column']=='comparative' and r['observationPeriod'] is None for r in rows))

class ReportIndexTests(unittest.TestCase):
 def test_success_failure_duplicate_not_silently_overwritten(self):
  from company_financial_report import report_index
  for rows in ([{'code':'600406','parseStatus':'parsed'},{'code':'600406','parseStatus':'failed'}],[{'code':'600406','parseStatus':'failed'},{'code':'600406','parseStatus':'parsed'}]):
   with self.assertRaisesRegex(ValueError,'记录重复'):report_index({'companies':rows})
 def test_empty_is_explicit_missing_and_invalid_schema_rejected(self):
  from company_financial_report import report_index
  self.assertEqual(report_index({'companies':[]}),{})
  with self.assertRaises(ValueError):report_index({'companies':None})
  with self.assertRaises(ValueError):report_index({'companies':[{}]})

class InputPathTests(unittest.TestCase):
 def test_input_references_relative_to_declared_base_and_not_mutated(self):
  from company_financial_report import resolve_input_paths
  import tempfile
  from pathlib import Path
  with tempfile.TemporaryDirectory() as directory:
   spec={'financialResult':'financial.json','originalResult':'originals/result.json','archives':['archive.json']};r=resolve_input_paths(spec,directory)
   self.assertEqual(r['archives'],[str(Path(directory)/'archive.json')]);self.assertEqual(spec['archives'],['archive.json']);self.assertEqual(Path(r['originalResult']),Path(directory)/'originals/result.json')
 def test_empty_path_rejected(self):
  from company_financial_report import resolve_input_paths
  with self.assertRaises(ValueError):resolve_input_paths({'financialResult':'','originalResult':'x','archives':[]},'.')


class QuarterCaptionTests(unittest.TestCase):
 def test_half_year_end_does_not_label_quarter_as_six_months(self):
  from company_financial_report import quarter_period_caption
  self.assertIn('2026-04-01至2026-06-30',quarter_period_caption('2026-06-30'))
  self.assertIn('2026-10-01至2026-12-31',quarter_period_caption('2026-12-31'))
  self.assertIn('不替代',quarter_period_caption('2026-03-31'))
  with self.assertRaises(ValueError):quarter_period_caption('2026-05-31')

class SampleValidityTests(unittest.TestCase):
 def test_nan_or_empty_valid_sample_not_reported_as_median(self):
  from company_financial_report import sample_commentary
  for value,valid,missing in [(float('nan'),1,0),(0.2,0,1),(None,1,0),(0.2,True,0)]:
   g=dict(group='测试',classificationVersion='v1',scope='consolidated',currency='CNY',sampleSize=1,changes={'revenue':{'yoy':dict(validCount=valid,missingCount=missing,median=value)}})
   with self.subTest(value=value,valid=valid),self.assertRaises(ValueError):sample_commentary(dict(period='2026-06-30',groups=[g]))

class SamplePeriodTests(unittest.TestCase):
 def test_group_changes_carry_quarter_period_not_halfyear(self):
  from company_financial_report import sample_commentary
  g=dict(group='测试',classificationVersion='v1',scope='consolidated',currency='CNY',sampleSize=1,changes={'revenue':{'yoy':dict(validCount=1,missingCount=0,median=0.186)}})
  lines,groups=sample_commentary(dict(period='2026-06-30',groups=[g]))
  self.assertIn('2026-04-01至2026-06-30',lines[0])
  self.assertIn('单季度营业收入同比为18.60%',lines[-1])
  self.assertEqual(groups[0]['entries'][0]['median'],0.186)
  g['sampleSize']=2;g['changes']['revenue']['yoy']['validCount']=2
  lines,_=sample_commentary(dict(period='2026-12-31',groups=[g]))
  self.assertIn('2026-10-01至2026-12-31',lines[0])
  self.assertIn('单季度营业收入同比样本中位数',lines[-1])
 def test_unknown_quarter_end_rejected_for_group_comparison(self):
  from company_financial_report import sample_commentary
  with self.assertRaises(ValueError):sample_commentary(dict(period='2026-05-31',groups=[]))

if __name__=='__main__':unittest.main()
