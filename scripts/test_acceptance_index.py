import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from acceptance_index import inspect_cases,human_brief,structure_checks,html_version_check
from report_content_review import REQUIRED


class AcceptanceTests(unittest.TestCase):
    def test_unanswered_questions_remain_gap_when_declared_checks_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);report=root/'report.md';report.write_text('现金为正。尚不能判断持续性。',encoding='utf-8');e=root/'e.json';e.write_text('{}')
            digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
            common=dict(reportPath=str(report),reportSha256=digest(report))
            review=dict(common,reviewer='human-review',checks=[dict(key=k,status='passed',location='正文',reason='声明检查') for k in REQUIRED])
            claims=dict(common,researchLevel='focused-appraisal',answeredQuestions=['现金规模'],unansweredQuestions=['持续性'],gapImpacts=[dict(missingData='结算明细',affectedQuestion='持续性',impact='尚不能判断持续性。',nextStep='核对回款付款期间')],claims=[dict(id='c',conclusion='现金为正。',limitations='所选期间',requiredEvidenceIds=['e'],evidence=[dict(id='e',path=str(e),sha256=digest(e),locator='输入')])])
            for name,value in [('review',review),('claims',claims)]:
                (root/(name+'.json')).write_text(json.dumps(value),encoding='utf-8-sig')
            result=inspect_cases([dict(scene='公司',case='测试',review=str(root/'review.json'),claims=str(root/'claims.json'))])
            row=result['cases'][0]
            self.assertEqual(row['issues'],[])
            self.assertEqual(row['status'],'valid-binding-with-content-gaps')
            self.assertTrue(any(x['key']=='unanswered-questions' for x in row['remainingChecks']));self.assertTrue(any(x['key']=='gap-next-step' for x in row['remainingChecks']))
            self.assertEqual(row['limitationDisclosureCoverage']['textBoundClaims'],0)
            self.assertTrue(any(x['key']=='claim-limitations' for x in row['remainingChecks']))
            self.assertIn('结论限制正文披露：0/1',human_brief(result))
            self.assertIn('缺少结算明细',human_brief(result))
            withdrawn=inspect_cases([dict(scene='公司',case='测试',review=str(root/'review.json'),claims=str(root/'claims.json'),invalidatedReason='新规则原文回放未通过')])
            self.assertEqual(withdrawn['cases'][0]['status'],'missing-or-invalid-binding')
            self.assertIn('新规则原文回放未通过',human_brief(withdrawn))
    def test_heading_with_populated_subsection_is_not_empty(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'r.md'
            p.write_text('# 报告\n## 判断\n结论与依据\n## 来源\n原件\n',encoding='utf-8')
            self.assertEqual(structure_checks(p)['issues'],[])

    def test_empty_subtree_and_sibling_boundary_remain_reported(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'r.md'
            p.write_text('# 报告\n## 空父章\n### 空子章\n## 下一章\n有内容\n',encoding='utf-8')
            self.assertEqual(structure_checks(p)['issues'],['空章节：空父章','空章节：空子章'])

    def test_relative_index_and_record_paths_resolve_from_their_files(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);record_dir=base/'records';record_dir.mkdir()
            report=base/'report.md';report.write_text('现金仍待验证',encoding='utf-8')
            evidence=record_dir/'e.json';evidence.write_text('{}',encoding='utf-8')
            digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
            common=dict(reportPath='../report.md',reportSha256=digest(report))
            review=dict(common,reviewer='AI-content-review',checks=[dict(key=k,status='passed',location='正文',reason='声明范围复查') for k in REQUIRED])
            claims=dict(common,researchLevel='focused-appraisal',answeredQuestions=['现金'],unansweredQuestions=['估值'],claims=[dict(id='c',conclusion='现金仍待验证',limitations='选定范围',evidence=[dict(path='e.json',sha256=digest(evidence),locator='已存输入')])])
            for name,data in [('review',review),('claims',claims)]:
                (record_dir/(name+'.json')).write_text(json.dumps(data),encoding='utf-8')
            row=inspect_cases([dict(scene='公司',case='相对路径',review='records/review.json',claims='records/claims.json')],base)['cases'][0]
            self.assertEqual(row['issues'],[])
            self.assertEqual(row['status'],'valid-binding-with-content-gaps')
            self.assertTrue(any(x['key']=='required-dependencies' for x in row['remainingChecks']))
            self.assertEqual(row['gapImpactCoverage']['uncoveredQuestions'],['估值'])
            self.assertTrue(any(x['key']=='gap-impact-coverage' for x in row['remainingChecks']))
            self.assertEqual(row['evidenceDependencyCoverage']['declaredClaims'],0)
            self.assertEqual(row['evidenceDependencyCoverage']['undeclaredClaims'][0]['id'],'c')
            self.assertEqual(row['pdfLocationCoverage']['claimsWithPdfLocators'],0)
            self.assertEqual(row['pdfLocationCoverage']['locatorItems'],0)
            brief=human_brief(dict(cases=[row]))
            self.assertIn('0/1条结论',brief)
            self.assertIn('核心依赖声明：0/1条',brief)
            self.assertIn('不是原文核验率或质量评分',brief)
            self.assertIn('可能使用网页、序列或其他证据',brief)
            self.assertIn('|关键未完成项|',brief)
            self.assertIn('|有限专题评价|估值|',brief)
            self.assertEqual(row['reportPath'],str(report.resolve()))
            self.assertEqual(json.loads((record_dir/'claims.json').read_text())['reportPath'],'../report.md')
            self.assertEqual(row['htmlLocationCoverage']['claimsWithHtmlLocators'],0)
            source=record_dir/'e.html';source.write_text('<p>价格结构不同</p>',encoding='utf-8')
            claims['claims'][0]['evidence'].append(dict(path='e.html',sha256=digest(source),locator='网页正文',htmlLocator=dict(quote='价格结构不同')))
            (record_dir/'claims.json').write_text(json.dumps(claims),encoding='utf-8')
            revised=inspect_cases([dict(scene='公司',case='网页定位',review='records/review.json',claims='records/claims.json')],base)['cases'][0]
            self.assertEqual(revised['issues'],[])
            self.assertEqual(revised['htmlLocationCoverage']['claimsWithHtmlLocators'],1)
            self.assertEqual(revised['htmlLocationCoverage']['locatorItems'],1)
            self.assertIn('网页原文引句检查：1条结论',human_brief(dict(cases=[revised])))
    def test_shorter_or_different_fence_does_not_expose_example(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'r.md'
            p.write_text('# 报告\n内容\n````md\n```\n~~~\n[x](missing-example.pdf)\n````\n## 原文\n[x](missing-real.pdf)\n',encoding='utf-8')
            self.assertEqual(structure_checks(p)['issues'],['本地链接不存在：missing-real.pdf'])

    def test_fence_with_trailing_text_does_not_close_example(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'r.md'
            p.write_text('# 报告\n内容\n~~~md\n~~~not-a-close\n[x](missing-example.pdf)\n~~~\n## 空章\n',encoding='utf-8')
            self.assertEqual(structure_checks(p)['issues'],['空章节：空章'])

    def test_html_current_body_and_stale_or_missing_delivery(self):
        from research_brief_html import render
        with tempfile.TemporaryDirectory() as d:
            md=Path(d)/'r.md';p=md.with_suffix('.html');md.write_text('# 判断\n有条件的结论',encoding='utf-8')
            self.assertEqual(html_version_check(md,p)['status'],'missing')
            p.write_text(render(md.read_text(encoding='utf-8'),title='标题 & 范围'),encoding='utf-8')
            self.assertEqual(html_version_check(md,p)['status'],'reproduced-from-current-markdown')
            md.write_text('# 判断\n已修正结论',encoding='utf-8')
            self.assertEqual(html_version_check(md,p)['status'],'different-from-current-render')
            p.write_text('<title>A</title><title>B</title>',encoding='utf-8')
            self.assertEqual(html_version_check(md,p)['status'],'unverifiable')
    def test_empty_sections_and_local_links_are_reported(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'r.md';p.write_text('# 报告\n内容\n## 缺口\n\n## 来源\n[原文](missing.pdf#page=2)\n',encoding='utf-8')
            checks=structure_checks(p)
            self.assertIn('空章节：缺口',checks['issues'])
            self.assertIn('本地链接不存在：missing.pdf#page=2',checks['issues'])

    def test_fenced_examples_and_external_links_are_not_local_failures(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'r.md';p.write_text('# 报告\n内容\n```md\n## 示例\n[x](missing.pdf)\n```\n[x](https://example.com)\n',encoding='utf-8')
            self.assertEqual(structure_checks(p)['issues'],[])
    def test_changed_body_and_evidence_invalidate_current_case(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            report = d / 'r.md'; report.write_text('现金转换偏弱', encoding='utf-8')
            evidence = d / 'e.json'; evidence.write_text('{}', encoding='utf-8')
            digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
            common = dict(reportPath=str(report), reportSha256=digest(report))
            review = dict(common, reviewer='AI-content-review', checks=[dict(key=k, status='partial' if k=='evidence' else 'passed', location='正文', reason='具体复查') for k in REQUIRED])
            claims = dict(common, researchLevel='focused-appraisal', answeredQuestions=['现金质量'], unansweredQuestions=['估值'], claims=[dict(id='c', conclusion='现金转换偏弱', limitations='仅本期', evidence=[dict(path=str(evidence), sha256=digest(evidence), locator='现金流字段')])])
            for name, value in [('review', review), ('claims', claims)]:
                (d / (name+'.json')).write_text(json.dumps(value), encoding='utf-8')
            case = dict(scene='公司', case='新样本', review=str(d/'review.json'), claims=str(d/'claims.json'))
            self.assertEqual(inspect_cases([case])['cases'][0]['status'], 'valid-binding-with-content-gaps')
            evidence.write_text('{"new":1}', encoding='utf-8')
            self.assertEqual(inspect_cases([case])['cases'][0]['status'], 'missing-or-invalid-binding')
            report.write_text('新正文', encoding='utf-8')
            self.assertIn('正文已变化', inspect_cases([case])['cases'][0]['issues'][0])

    def test_missing_records_are_not_accepted(self):
        row = inspect_cases([dict(scene='行业', case='待补')])['cases'][0]
        self.assertEqual(row['status'], 'missing-or-invalid-binding')
        self.assertFalse(row['semanticCertification'])

    def test_human_brief_does_not_promote_partial_or_visual_acceptance(self):
        result=dict(cases=[dict(scene='ETF',case='510880',status='valid-binding-with-content-gaps',
                    researchLevel='focused-appraisal',issues=[],answeredQuestions=['股票敞口'],
                    unansweredQuestions=['跟踪质量'],remainingChecks=[dict(reason='缺总收益指数')])])
        text=human_brief(result)
        self.assertIn('版本有效，内容仍有缺口',text)
        self.assertIn('跟踪质量',text);self.assertIn('视觉验收：本次检查未验证',text)

    def test_invalid_record_does_not_show_stale_answer(self):
        r=inspect_cases([dict(scene='公司|研究',case='失效记录')]);r['cases'][0]['answeredQuestions']=['旧结论']
        r['cases'][0]['evidenceDependencyCoverage']=dict(totalClaims=99,declaredClaims=99)
        text=human_brief(r)
        self.assertNotIn('旧结论',text);self.assertIn('需重验',text)
        self.assertIn('公司／研究',text)
        self.assertIn('核心依赖声明：0/0条',text)


class EncodingIsolationTests(unittest.TestCase):
 def test_bad_encoded_record_reports_failure_without_aborting_other_cases(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'bad.json';p.write_bytes(b'\xff\xfe\x80')
   rows=inspect_cases([dict(scene='公司',case='损坏编码',review=str(p),claims=str(p)),dict(scene='基金',case='下一案例')])['cases']
   self.assertEqual(len(rows),2)
   self.assertEqual(rows[0]['status'],'missing-or-invalid-binding')
   self.assertEqual(len(rows[0]['issues']),2)
   self.assertEqual(rows[1]['case'],'下一案例')
   self.assertEqual(p.read_bytes(),b'\xff\xfe\x80')

if __name__ == '__main__':
    unittest.main()
