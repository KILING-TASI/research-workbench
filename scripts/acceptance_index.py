"""Recheck current report/evidence bindings without certifying research judgments."""
import argparse
import json
import re
import html
import hashlib
from pathlib import Path
from urllib.parse import unquote, urlsplit
from report_content_review import bind_review, bind_claims
from collection_validation import unique_pairs,reject_constant,finite_json_float

def html_version_check(markdown_path,html_path):
    from research_brief_html import render
    md=Path(markdown_path);p=Path(html_path)
    if not p.exists():return dict(status='missing',path=str(p),scope='HTML交付文件缺失；不影响Markdown正文绑定')
    actual=p.read_text(encoding='utf-8');titles=re.findall(r'<title>(.*?)</title>',actual,re.S)
    if len(titles)!=1:return dict(status='unverifiable',path=str(p),scope='无法识别唯一网页标题，不认定版本一致')
    expected=render(md.read_text(encoding='utf-8'),title=html.unescape(titles[0]))
    return dict(status='reproduced-from-current-markdown' if actual==expected else 'different-from-current-render',path=str(p.resolve()),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),scope='用当前渲染器重现HTML全文；不验证视觉、浏览器行为或判断正确性')


def structure_checks(path):
    """Check Markdown headings and inline local links, not semantic quality."""
    path=Path(path); text=path.read_text(encoding='utf-8'); lines=text.splitlines()
    visible=[]; fence=None
    for line in lines:
        marker=re.match(r'^( {0,3})(`{3,}|~{3,})(.*)$',line)
        if fence is not None:
            if marker and marker[2][0]==fence[0] and len(marker[2])>=fence[1] and not marker[3].strip():
                fence=None
            continue
        if marker:
            fence=(marker[2][0],len(marker[2]));continue
        visible.append(line)
    issues=[]
    for i,line in enumerate(visible):
        heading=re.match(r'^(#{1,6})\s+\S',line)
        if heading:
            content=False
            for following in visible[i+1:]:
                child=re.match(r'^(#{1,6})\s+\S',following)
                if child:
                    if len(child[1])<=len(heading[1]):break
                    continue
                if following.strip():
                    content=True;break
            if not content:
                issues.append('空章节：'+line.lstrip('#').strip())
    for target in re.findall(r'\]\((<[^>]+>|[^\s)]+)\)', '\n'.join(visible)):
        target=target.strip('<>'); parsed=urlsplit(target)
        if parsed.scheme or parsed.netloc or not parsed.path: continue
        if not (path.parent/unquote(parsed.path)).exists():
            issues.append('本地链接不存在：'+target)
    return dict(issues=list(dict.fromkeys(issues)),scope='Markdown空章节及行内本地链接；不验证网页、锚点、视觉或论证充分性')


def human_brief(result):
    """Describe validated scope and remaining work; never infer full acceptance."""
    labels={'missing-or-invalid-binding':'记录缺失或失效，需重验',
            'valid-binding-with-content-gaps':'版本有效，内容仍有缺口',
            'valid-binding-declared-review-passed':'版本有效，声明的内容复查通过'}
    levels={'data-check':'资料核对','historical-comparison':'历史比较',
            'focused-appraisal':'有限专题评价','deep-research':'深度研究声明'}
    def clean(v):
        return str(v).replace('|','／').replace('\r',' ').replace('\n',' ').replace('<','＜').replace('>','＞')
    rows=result['cases'];invalid=sum(x['status']=='missing-or-invalid-binding' for x in rows)
    gaps=sum(x['status']=='valid-binding-with-content-gaps' for x in rows)
    valid=[r for r in rows if not r['issues']]
    total=sum(r.get('evidenceDependencyCoverage',{}).get('totalClaims',0) for r in valid)
    declared=sum(r.get('evidenceDependencyCoverage',{}).get('declaredClaims',0) for r in valid)
    out=['# 最新研究报告验收清单','',
         '> 当前'+str(len(rows))+'个案例中，'+str(invalid)+'个记录缺失或失效，'+str(gaps)+'个版本有效但仍有内容缺口。',
         '', '本页区分报告版本有效、已回答问题与尚未完成的评价。内容复查是逐项声明，不等于判断正确率；视觉效果另行验收。',
         '', '当前有效版本的核心依赖声明：'+str(declared)+'/'+str(total)+'条；失效记录不纳入统计。这是依赖绑定数量，不是原文核验率或研究质量评分。',
         '', '|场景|案例|当前状态|研究范围|关键未完成项|', '|---|---|---|---|---|']
    for r in rows:
        # Invalid records must not expose stale research scope as current work.
        pending='先重新核验正文与证据' if r['issues'] else '；'.join(r.get('unansweredQuestions',[])[:2]) or '未列缺口，仍需审阅完成范围'
        out.append('|'+ '|'.join(clean(v) for v in [r['scene'],r['case'],labels[r['status']],levels.get(r.get('researchLevel'),'尚不能确认'),pending])+'|')
    for r in rows:
        out+=['','## '+clean(r['scene'])+'：'+clean(r['case']),'']
        if r['issues']:
            out+=['原记录不能作为当前报告验收依据。']+['- '+clean(x) for x in r['issues']]
            # Never present stale questions as current accepted findings.
            continue
        out+=['**已回答的问题**：'+ '；'.join(clean(x) for x in r['answeredQuestions'])+'。','']
        questions=r['unansweredQuestions']
        out+=['**尚不能回答**：'+('；'.join(clean(x) for x in questions)+'。' if questions else '记录未列未回答问题；这不自动证明完整评价已完成。'),'']
        for gap in r.get('gapImpacts') or []:
            out+=['- 缺少'+clean(gap['missingData'])+'：'+clean(gap['impact'])+' 下一步：'+clean(gap['nextStep'])]
        for item in r['remainingChecks']:
            out.append('- '+clean(item['reason']))
        disclosure=r.get('limitationDisclosureCoverage')
        if disclosure:out+=['','结论限制正文披露：'+str(disclosure['textBoundClaims'])+'/'+str(disclosure['totalClaims'])+'条已定位；文字出现不证明限制说明充分。']
        coverage=r.get('evidenceDependencyCoverage')
        if coverage:
            out+=['','必需证据声明：'+str(coverage['declaredClaims'])+'/'+str(coverage['totalClaims'])+'条结论已声明并通过依赖绑定；不是原文核验率或质量评分。']
            if coverage['undeclaredClaims']:
                out+=['尚未声明必需依赖的结论：']+['- '+clean(x['conclusion']) for x in coverage['undeclaredClaims']]
        original=r.get('pdfLocationCoverage')
        if original:
            out+=['','PDF原页引句检查：'+str(original['claimsWithPdfLocators'])+'条结论包含实际检查的原页定位，共'+str(original['locatorItems'])+'项；不代表整份原文核验。']
            if original['claimsWithoutPdfLocators']:
                out+=['以下结论未启用PDF原页引句检查（可能使用网页、序列或其他证据，须按来源判断）：']+['- '+clean(x['conclusion']) for x in original['claimsWithoutPdfLocators']]
        webpage=r.get('htmlLocationCoverage')
        if webpage:
            out+=['','网页原文引句检查：'+str(webpage['claimsWithHtmlLocators'])+'条结论包含实际检查的网页定位，共'+str(webpage['locatorItems'])+'项；只核对归档文本位置，不是网页视觉或判断正确率。']
        structural=r.get('structureChecks')
        if structural:
            out+=['','结构检查：'+('；'.join(clean(x) for x in structural['issues']) if structural['issues'] else '未发现空章节或失效的行内本地链接；不代表内容与视觉通过。')]
        if r.get('htmlVersionCheck'):
            out+=['','网页版本检查：'+clean(r['htmlVersionCheck']['status'])+'；不等于视觉验收。']
        out+=['','视觉验收：本次检查未验证。']
        path=r.get('reportPath')
        if path:
            out+=['','当前正文：['+clean(Path(path).name)+'](<'+str(Path(path).resolve()).replace('>','%3E')+'>)。']
    out+=['','证据文件、字段位置或正文变化后，应重新检查并重新复查相关结论。有效绑定不替代数据真实性、经济因果或完整研究判断。']
    return '\n'.join(out)+'\n'


def inspect_cases(cases,base_dir=None):
    rows = []
    for case in cases:
        case=dict(case)
        if base_dir is not None:
            for key in ('review','claims','htmlPath'):
                if case.get(key) and not Path(case[key]).is_absolute():
                    case[key]=str((Path(base_dir)/case[key]).resolve())
        row = dict(scene=case['scene'], case=case['case'], issues=[], semanticCertification=False)
        if 'invalidatedReason' in case:
            reason=case['invalidatedReason']
            if not isinstance(reason,str) or not reason.strip():raise ValueError('报告撤回原因须为非空文字')
            row['issues'].append('已有验收结论撤回：'+reason)
        records = {}
        for key, validator in [('review', bind_review), ('claims', bind_claims)]:
            path = case.get(key)
            if not path:
                row['issues'].append(key + ': 尚未提供记录')
                continue
            try:
                record_path=Path(path).resolve()
                spec=json.loads(record_path.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)
                if spec.get('reportPath') and not Path(spec['reportPath']).is_absolute():
                    spec['reportPath']=str((record_path.parent/spec['reportPath']).resolve())
                for claim in spec.get('claims',[]):
                    for evidence in claim.get('evidence',[]):
                        if evidence.get('path') and not Path(evidence['path']).is_absolute():
                            evidence['path']=str((record_path.parent/evidence['path']).resolve())
                records[key] = validator(spec)
            except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
                row['issues'].append(key + ': ' + str(exc))
        if len(records) == 2:
            a, b = records['review'], records['claims']
            if a['reportPath'] != b['reportPath'] or a['reportSha256'] != b['reportSha256']:
                row['issues'].append('复查与结论绑定不是同一份正文')
            row.update(reportPath=a['reportPath'], reportSha256=a['reportSha256'],
                       researchLevel=b['researchLevel'], answeredQuestions=b['answeredQuestions'],
                       unansweredQuestions=b['unansweredQuestions'],
                       remainingChecks=[x for x in a['checks'] if x['status'] in ('partial', 'failed')])
            row['gapImpacts']=b.get('gapImpacts')
            row['gapImpactStatus']=b.get('gapImpactStatus','not-declared')
            row['gapNextStepDisclosure']=b.get('gapNextStepDisclosure',[])
            covered_questions={g['affectedQuestion'] for g in b.get('gapImpacts') or []}
            uncovered_questions=[q for q in b['unansweredQuestions'] if q not in covered_questions]
            row['gapImpactCoverage']=dict(totalQuestions=len(b['unansweredQuestions']),coveredQuestions=len(b['unansweredQuestions'])-len(uncovered_questions),uncoveredQuestions=uncovered_questions,scope='仅缺口影响与补取路径登记，不认证语义充分性')
            if uncovered_questions:row['remainingChecks'].append(dict(key='gap-impact-coverage',status='partial',reason='未回答问题尚未逐项关联缺口影响与补取路径：'+'；'.join(uncovered_questions)))
            pending_paths=[g['affectedQuestion'] for g in row['gapNextStepDisclosure'] if g['status']!='text-bound']
            if pending_paths:row['remainingChecks'].append(dict(key='gap-next-step',status='partial',reason='补取路径已登记但正文未定位：'+'；'.join(pending_paths)))
            if b['unansweredQuestions']:
                row['remainingChecks'].append(dict(key='unanswered-questions',status='partial',reason='尚未回答的研究问题：'+'；'.join(b['unansweredQuestions'])))
            undisclosed=[dict(id=c['id'],conclusion=c['conclusion'],limitations=c['limitations']) for c in b['claims'] if c.get('limitationDisclosureStatus')!='text-bound']
            row['limitationDisclosureCoverage']=dict(totalClaims=len(b['claims']),textBoundClaims=len(b['claims'])-len(undisclosed),unlocatedClaims=undisclosed,scope='仅逐条限制文字是否在正文出现，不评价披露充分性')
            if undisclosed:row['remainingChecks'].append(dict(key='claim-limitations',status='partial',reason='结论限制已登记但未在正文定位：'+'、'.join(c['id'] for c in undisclosed)+'；需向读者披露后重验。'))
            undeclared=[dict(id=c['id'],conclusion=c['conclusion']) for c in b['claims'] if not c.get('requiredEvidenceIds')]
            row['evidenceDependencyCoverage']=dict(totalClaims=len(b['claims']),declaredClaims=len(b['claims'])-len(undeclared),undeclaredClaims=undeclared,scope='仅已声明的依赖绑定；不按文件扩展名推断原文真实性或完整性')
            if undeclared:
                row['remainingChecks'].append(dict(key='required-dependencies',status='partial',reason='核心结论尚未声明必需依赖：'+'、'.join(c['id'] for c in undeclared)+'；现有来源文件绑定不代替依赖完整性。'))
            unlocated=[dict(id=c['id'],conclusion=c['conclusion']) for c in b['claims'] if not any('pdfLocator' in e for e in c['evidence'])]
            row['pdfLocationCoverage']=dict(claimsWithPdfLocators=len(b['claims'])-len(unlocated),locatorItems=sum('pdfLocator' in e for c in b['claims'] for e in c['evidence']),claimsWithoutPdfLocators=unlocated,scope='仅显式PDF页引句检查；非PDF证据不自动视为缺失或失败')
            row['htmlLocationCoverage']=dict(claimsWithHtmlLocators=sum(any('htmlLocator' in e for e in c['evidence']) for c in b['claims']),locatorItems=sum('htmlLocator' in e for c in b['claims'] for e in c['evidence']),scope='仅已声明的归档HTML引句位置；没有定位不自动失败，不验证动态页面或视觉效果')
            row['structureChecks']=structure_checks(a['reportPath'])
            if case.get('htmlPath'):
                try:row['htmlVersionCheck']=html_version_check(a['reportPath'],case['htmlPath'])
                except (OSError,ValueError) as exc:row['htmlVersionCheck']=dict(status='unverifiable',reason=str(exc))
                if row['htmlVersionCheck']['status']!='reproduced-from-current-markdown':
                    row['remainingChecks'].append(dict(key='html-version',status='failed',reason='HTML未能从当前正文重现：'+row['htmlVersionCheck']['status']))
            if row['structureChecks']['issues']:
                row['remainingChecks'].append(dict(key='structure',status='failed',reason='；'.join(row['structureChecks']['issues'])))
        row['status'] = ('missing-or-invalid-binding' if row['issues'] else
                         'valid-binding-with-content-gaps' if row['remainingChecks'] else
                         'valid-binding-declared-review-passed')
        # Visual acceptance is deliberately separate; no screenshot is inferred.
        row['visualStatus'] = 'not-verified-by-this-check'
        rows.append(row)
    return dict(cases=rows, scope='核对当前正文、证据文件与复查记录是否一致；不自动认证判断质量或视觉效果')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('input')
    p.add_argument('--output', required=True)
    p.add_argument('--brief', help='新Markdown清单路径')
    args = p.parse_args()
    result = inspect_cases(json.loads(Path(args.input).read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)['cases'],Path(args.input).resolve().parent)
    with Path(args.output).open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    if args.brief:
        with Path(args.brief).open('x',encoding='utf-8') as f:
            f.write(human_brief(result))
