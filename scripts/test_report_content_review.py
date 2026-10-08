import json
import unittest,tempfile,hashlib
from pathlib import Path
from report_content_review import bind_review,bind_claims,json_value_at,REQUIRED,verify_snapshot_binding
class Tests(unittest.TestCase):
 def test_json_exponent_overflow_cannot_be_bound_as_matching_value(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'r.md';p.write_text('选定值一致',encoding='utf-8');e=Path(d)/'e.json'
   for token in ['1e999','-1e999','NaN','Infinity']:
    e.write_text('{"value":'+token+'}',encoding='utf-8')
    item=dict(path=str(e),sha256=hashlib.sha256(e.read_bytes()).hexdigest(),locator='值',jsonPointer='/value',expectedValue=float('inf'))
    spec=dict(reportPath=str(p),reportSha256=hashlib.sha256(p.read_bytes()).hexdigest(),researchLevel='data-check',answeredQuestions=['值'],unansweredQuestions=[],claims=[dict(id='c',conclusion='选定值一致',limitations='选定范围',evidence=[item])])
    with self.subTest(token=token),self.assertRaises(ValueError):bind_claims(spec)
   e.write_text('{"value":1.5}',encoding='utf-8');item['sha256']=hashlib.sha256(e.read_bytes()).hexdigest();item['expectedValue']=1.5
   bind_claims(spec)
   item['expectedValue']={'nested':float('nan')}
   with self.assertRaises(ValueError):bind_claims(spec)
 def test_snapshot_version_and_missing_dependency(self):
  with tempfile.TemporaryDirectory() as d:
   folder=Path(d);report=folder/'r.md';report.write_text('结论',encoding='utf-8');e=folder/'e.json';e.write_text('{}',encoding='utf-8');p=folder/'binding.json'
   record={'reportPath':'r.md','reportSha256':hashlib.sha256(report.read_bytes()).hexdigest(),'evidence':[{'id':'e','path':'e.json','sha256':hashlib.sha256(e.read_bytes()).hexdigest()}],'conclusions':[{'id':'c','requiredEvidenceIds':['e']}]}
   p.write_text(json.dumps(record),encoding='utf-8');self.assertEqual(verify_snapshot_binding(p)['conclusionCount'],1)
   e.write_text('{"changed":true}',encoding='utf-8')
   with self.assertRaisesRegex(ValueError,'证据版本'):verify_snapshot_binding(p)
   e.write_text('{}',encoding='utf-8');record['conclusions'][0]['requiredEvidenceIds']=['missing'];p.write_text(json.dumps(record),encoding='utf-8')
   with self.assertRaisesRegex(ValueError,'依赖'):verify_snapshot_binding(p)

 def test_question_lists_cannot_contradict(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'r.md';p.write_text('结论',encoding='utf8');s=dict(reportPath=str(p),reportSha256=hashlib.sha256(p.read_bytes()).hexdigest(),researchLevel='focused-appraisal',answeredQuestions=['同一问题'],unansweredQuestions=['同一问题'],claims=[])
   with self.assertRaisesRegex(ValueError,'不交叉'):bind_claims(s)
 def test_malformed_records_rejected_explicitly(self):
  for spec in [None,[],{},dict(reportPath=True)]:
   for function in [bind_review,bind_claims]:
    with self.subTest(spec=spec,function=function.__name__),self.assertRaises(ValueError):function(spec)
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'report.md';p.write_text('结论',encoding='utf-8');base=dict(reportPath=str(p),reportSha256=hashlib.sha256(p.read_bytes()).hexdigest())
   with self.assertRaisesRegex(ValueError,'复查条目'):bind_review(dict(base,reviewer='human-review',checks=[None]))
   spec=dict(base,researchLevel='focused-appraisal',answeredQuestions=['问题'],unansweredQuestions=[],claims=[None])
   with self.assertRaisesRegex(ValueError,'结论条目'):bind_claims(spec)
   spec['claims']=[dict(id='c',conclusion='结论',limitations='范围',evidence=[None])]
   with self.assertRaisesRegex(ValueError,'证据条目'):bind_claims(spec)
 def test_gap_impact_requires_unanswered_question_and_body_disclosure(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);report=root/'report.md';report.write_text('现金仍需观察。尚不能判断现金改善能否持续。',encoding='utf-8');e=root/'input.json';e.write_text('{}')
   gap=dict(missingData='回款及付款明细',affectedQuestion='现金改善持续性',impact='尚不能判断现金改善能否持续。',nextStep='核对现金补充资料及结算说明')
   spec=dict(reportPath=str(report),reportSha256=hashlib.sha256(report.read_bytes()).hexdigest(),researchLevel='focused-appraisal',answeredQuestions=['现金规模'],unansweredQuestions=['现金改善持续性'],gapImpacts=[gap],claims=[dict(id='cash',conclusion='现金仍需观察。',limitations='所选区间',evidence=[dict(path=str(e),sha256=hashlib.sha256(e.read_bytes()).hexdigest(),locator='输入')])])
   self.assertEqual(bind_claims(spec)['gapImpactStatus'],'declared-and-text-bound')
   self.assertEqual(bind_claims(spec)['gapNextStepDisclosure'][0]['status'],'registered-not-located-in-body')
   gap['nextStepQuote']='尚不能判断现金改善能否持续。'
   self.assertEqual(bind_claims(spec)['gapNextStepDisclosure'][0]['status'],'text-bound')
   gap['nextStepQuote']='未出现的补取句'
   with self.assertRaisesRegex(ValueError,'补取路径原句'):bind_claims(spec)
   gap.pop('nextStepQuote')
   for field,value in [('affectedQuestion','现金规模'),('impact','现金改善一定持续'),('nextStep','')]:
    bad=dict(spec,gapImpacts=[dict(gap,**{field:value})])
    with self.subTest(field=field),self.assertRaises(ValueError):bind_claims(bad)
 def test_html_quote_requires_prose_not_script_or_style(self):
  with tempfile.TemporaryDirectory() as folder:
   d=Path(folder);p=d/'report.md';p.write_text('价格结构不同',encoding='utf-8')
   h=d/'source.html';h.write_text('<head><title>标题66%</title><script>嵌套55%</script></head><script>假指标99%</script><style>假指标88%</style><template>模板77%</template><p>食品价格\n下降1.4% &amp; 非食品上涨</p>',encoding='utf-8')
   e=dict(path=str(h),sha256=hashlib.sha256(h.read_bytes()).hexdigest(),locator='正文',htmlLocator=dict(quote='食品价格下降1.4% & 非食品上涨'))
   s=dict(reportPath=str(p),reportSha256=hashlib.sha256(p.read_bytes()).hexdigest(),researchLevel='data-check',answeredQuestions=['价格'],unansweredQuestions=['因果'],claims=[dict(id='c',conclusion='价格结构不同',limitations='仅引句位置',evidence=[e])])
   bind_claims(s)
   for quote in ['标题66%','嵌套55%','假指标99%','假指标88%','模板77%','食品价格下降2.4%',' ']:
    e['htmlLocator']['quote']=quote
    with self.subTest(quote=quote),self.assertRaises(ValueError):bind_claims(s)
 def test_missing_pdf_dependency_is_explicit_not_accepted(self):
  import sys
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);pdf=d/'source.pdf';pdf.write_bytes(b'%PDF-missing-runtime-fixture');p=d/'r.md';p.write_text('结论',encoding='utf-8')
   s=dict(reportPath=str(p),reportSha256=hashlib.sha256(p.read_bytes()).hexdigest(),researchLevel='data-check',answeredQuestions=['原文'],unansweredQuestions=['全部数据'],claims=[dict(id='c',conclusion='结论',limitations='所选范围',evidence=[dict(path=str(pdf),sha256=hashlib.sha256(pdf.read_bytes()).hexdigest(),locator='第1页',pdfLocator=dict(page=1,quote='文字'))])])
   with patch.dict(sys.modules,{'pypdf':None}):
    with self.assertRaisesRegex(ValueError,'PDF原页读取失败'):bind_claims(s)
 def test_pdf_quote_must_match_specified_physical_page(self):
  from pypdf import PdfWriter
  from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);pdf=d/'source.pdf';writer=PdfWriter();page=writer.add_blank_page(width=300,height=300)
   font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
   page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
   stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 10 200 Td (Issuer A shares 123456) Tj ET');page[NameObject('/Contents')]=writer._add_object(stream);writer.add_blank_page(width=300,height=300)
   with pdf.open('wb') as f:writer.write(f)
   p=d/'r.md';p.write_text('发行人身份已核',encoding='utf-8');e=dict(path=str(pdf),sha256=hashlib.sha256(pdf.read_bytes()).hexdigest(),locator='物理第1页',pdfLocator=dict(page=1,quote='Issuer A shares 123456'))
   s=dict(reportPath=str(p),reportSha256=hashlib.sha256(p.read_bytes()).hexdigest(),researchLevel='data-check',answeredQuestions=['身份'],unansweredQuestions=['全部财务'],claims=[dict(id='c',conclusion='发行人身份已核',limitations='所选引句',evidence=[e])])
   bind_claims(s)
   for bad in [dict(page=2,quote='Issuer A shares 123456'),dict(page=3,quote='Issuer A shares 123456'),dict(page=True,quote='Issuer A shares 123456'),dict(page=1,quote='Issuer A shares 654321')]:
    e['pdfLocator']=bad
    with self.assertRaises(ValueError):bind_claims(s)
 def test_claim_in_fenced_example_is_not_report_conclusion(self):
  for fence in ('```','~~~~'):
   with self.subTest(fence=fence),tempfile.TemporaryDirectory() as d:
    p=Path(d)/'r.md';e=Path(d)/'e.json';e.write_text('{}',encoding='utf-8')
    body='# 报告\n'+fence+'md\n现金需要观察\n'+fence+'\n其他正文'
    p.write_text(body,encoding='utf-8')
    s=dict(reportPath=str(p),reportSha256=hashlib.sha256(p.read_bytes()).hexdigest(),researchLevel='focused-appraisal',answeredQuestions=['现金'],unansweredQuestions=['估值'],claims=[dict(id='c',conclusion='现金需要观察',limitations='选定范围',evidence=[dict(path=str(e),sha256=hashlib.sha256(e.read_bytes()).hexdigest(),locator='输入')])])
    with self.assertRaisesRegex(ValueError,'结论未出现在绑定正文'):bind_claims(s)
    p.write_text(body+'\n> 现金需要观察',encoding='utf-8');s['reportSha256']=hashlib.sha256(p.read_bytes()).hexdigest();bind_claims(s)
 def test_required_original_dependency_cannot_be_replaced_by_calculation(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'r.md';p.write_text('选定结论',encoding='utf-8');e=Path(d)/'e.json';e.write_text('{}',encoding='utf-8')
   item=dict(path=str(e),sha256=hashlib.sha256(e.read_bytes()).hexdigest(),locator='选定输入')
   row=dict(id='c',conclusion='选定结论',limitations='仅验证依赖绑定',requiredEvidenceIds=['original','calculation'],evidence=[dict(item,id='calculation')])
   s=dict(reportPath=str(p),reportSha256=hashlib.sha256(p.read_bytes()).hexdigest(),researchLevel='focused-appraisal',answeredQuestions=['选定问题'],unansweredQuestions=['完整研究'],claims=[row])
   with self.assertRaisesRegex(ValueError,'必需证据缺失'):bind_claims(s)
   row['evidence'].append(dict(item,id='original'));self.assertFalse(bind_claims(s)['semanticCertification'])
   row['evidence'].append(dict(item,id='original'))
   with self.assertRaisesRegex(ValueError,'证据编号为空或重复'):bind_claims(s)
   row['evidence'].pop();row['requiredEvidenceIds']=['original','original']
   with self.assertRaisesRegex(ValueError,'必需证据编号'):bind_claims(s)
 def test_quote_must_be_in_unique_named_section_not_example(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'r.md';p.write_text('## 结论\n现金仍需观察\n```\n示例引句\n```\n## 证据\n其他章节文字',encoding='utf-8')
   s=dict(reportPath=str(p),reportSha256=hashlib.sha256(p.read_bytes()).hexdigest(),reviewer='AI-content-review',checks=[dict(key=k,status='passed',location='结论段',sectionHeading='结论',sectionQuote='现金仍需观察',reason='限定现金解释') for k in REQUIRED])
   bind_review(s)
   for bad in ('其他章节文字','示例引句',' '):
    s['checks'][0]['sectionQuote']=bad
    with self.assertRaises(ValueError):bind_review(s)
   s['checks'][0]['sectionQuote']='现金仍需观察';p.write_text(p.read_text(encoding='utf-8')+'\n## 结论\n重复章节',encoding='utf-8');s['reportSha256']=hashlib.sha256(p.read_bytes()).hexdigest()
   with self.assertRaisesRegex(ValueError,'唯一章节'):bind_review(s)
 def test_short_or_annotated_fences_do_not_expose_fake_sections(self):
  for close in ('```','```` trailing','~~~','    ````'):
   with self.subTest(close=close),tempfile.TemporaryDirectory() as d:
    p=Path(d)/'r.md';p.write_text('## 当前结论\n````python\n'+close+'\n## 伪章节\n````\n## 真章节',encoding='utf-8')
    s=dict(reportPath=str(p),reportSha256=hashlib.sha256(p.read_bytes()).hexdigest(),reviewer='AI-content-review',checks=[dict(key=k,status='passed',location='真章节',sectionHeading='真章节',reason='核对当前章节') for k in REQUIRED])
    bind_review(s);s['checks'][0]['sectionHeading']='伪章节'
    with self.assertRaisesRegex(ValueError,'章节不在当前正文'):bind_review(s)
 def test_review_section_must_exist_in_current_body(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'r.md';p.write_text('## 当前结论\n正文\n```\n## 旧结论\n```',encoding='utf-8')
   s=dict(reportPath=str(p),reportSha256=hashlib.sha256(p.read_bytes()).hexdigest(),reviewer='AI-content-review',checks=[dict(key=k,status='passed',location='当前结论',sectionHeading='当前结论',reason='本段有限复查') for k in REQUIRED])
   bind_review(s);s['checks'][0]['sectionHeading']='旧结论'
   with self.assertRaisesRegex(ValueError,'章节不在当前正文'):bind_review(s)
 def test_binding_and_rejections(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'r.md';p.write_text('结论及证据',encoding='utf-8');s=dict(reportPath=str(p),reportSha256=hashlib.sha256(p.read_bytes()).hexdigest(),reviewer='AI-content-review',checks=[dict(key=k,status='passed',location='正文段落',reason='明确记录的复查理由') for k in REQUIRED])
   self.assertFalse(bind_review(s)['semanticCertification'])
   s['checks'][0]['status']='partial';self.assertEqual(bind_review(s)['status'],'partial-or-failed')
   s['checks'][0]['reason']=' '
   with self.assertRaises(ValueError):bind_review(s)
   s['checks'][0]['reason']='复查理由';s['checks'].pop()
   with self.assertRaises(ValueError):bind_review(s)
   p.write_text('新的结论',encoding='utf-8')
   with self.assertRaises(ValueError):bind_review(s)
class ClaimTests(unittest.TestCase):
 def test_json_pointer_and_invalid_paths(self):
  self.assertEqual(json_value_at({'a/b':{'~x':[7]}},'/a~1b/~0x/0'),7)
  for ptr in ['/missing','/a~2b','/list/01','/list/-','/list/2']:
   with self.assertRaises(ValueError):json_value_at({'list':[True]},ptr)
 def test_json_value_binding_not_only_file_hash(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'r.md';p.write_text('选定值一致',encoding='utf8');e=Path(d)/'e.json';e.write_text('{"matched":true}',encoding='utf8')
   item=dict(path=str(e),sha256=hashlib.sha256(e.read_bytes()).hexdigest(),locator='匹配状态',jsonPointer='/matched',expectedValue=True)
   s=dict(reportPath=str(p),reportSha256=hashlib.sha256(p.read_bytes()).hexdigest(),researchLevel='data-check',answeredQuestions=['是否匹配'],unansweredQuestions=['全量是否完整'],claims=[dict(id='match',conclusion='选定值一致',limitations='选定值',evidence=[item])])
   bind_claims(s)
   item['expectedValue']=1
   with self.assertRaises(ValueError):bind_claims(s)
   item.pop('expectedValue')
   with self.assertRaises(ValueError):bind_claims(s)
 def test_evidence_change_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'r.md';p.write_text('现金兑现仍需观察',encoding='utf-8');e=Path(d)/'e.json';e.write_text('{}')
   s=dict(reportPath=str(p),reportSha256=hashlib.sha256(p.read_bytes()).hexdigest(),researchLevel='focused-appraisal',answeredQuestions=['现金兑现情况'],unansweredQuestions=['估值'],claims=[dict(id='cash',conclusion='现金兑现仍需观察',limitations='只评价披露期',evidence=[dict(path=str(e),sha256=hashlib.sha256(e.read_bytes()).hexdigest(),locator='现金流字段')])])
   row=s['claims'][0];row['limitationQuote']='现金兑现仍需观察';self.assertEqual(bind_claims(s)['claims'][0]['limitationDisclosureStatus'],'text-bound')
   row['limitationQuote']='正文不存在的局限'
   with self.assertRaisesRegex(ValueError,'限制原句'):bind_claims(s)
   row.pop('limitationQuote')
   self.assertFalse(bind_claims(s)['semanticCertification']);e.write_text('{"changed":true}')
   with self.assertRaises(ValueError):bind_claims(s)
 def test_scope_and_missing_support_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'r.md';p.write_text('结论',encoding='utf-8')
   s=dict(reportPath=str(p),reportSha256=hashlib.sha256(p.read_bytes()).hexdigest(),researchLevel='focused-appraisal',answeredQuestions=['问题'],unansweredQuestions=[],claims=[dict(id='x',conclusion='结论',limitations='局限',evidence=[])])
   with self.assertRaises(ValueError):bind_claims(s)
   s['researchLevel']='complete-certified'
   with self.assertRaises(ValueError):bind_claims(s)
if __name__=='__main__':unittest.main()
