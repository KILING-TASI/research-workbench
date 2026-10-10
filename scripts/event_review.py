"""Bounded explicit event associations; no rule verdict or automatic event discovery."""
import argparse,json,re,hashlib
from pathlib import Path
from urllib.parse import urlparse
from inquiry_review import day
from report_access.original_pages import InRunPDFPages
from collection_validation import unique_pairs,reject_constant

KINDS={'inquiry','reply','penalty','audit-opinion','auditor-change','correction','restatement'}
LABELS={'inquiry':'问询线索','reply':'回复','penalty':'处罚文件','audit-opinion':'审计意见','auditor-change':'审计师变更','correction':'更正','restatement':'重述'}

def review(spec):
    entity=spec['entity'];cutoff=day(spec['asOf']);docs={};cache=InRunPDFPages()
    if not isinstance(entity,str) or not entity.strip():raise ValueError('主体缺失')
    documents=spec['documents'];events=spec['events'];relations=spec.get('relations',[])
    if not isinstance(documents,list) or not 1<=len(documents)<=100 or not isinstance(events,list) or not 1<=len(events)<=500 or not isinstance(relations,list) or len(relations)>1000:raise ValueError('列表范围无效')
    for doc in documents:
        key=doc['id'];url=urlparse(doc['source'])
        if not isinstance(key,str) or not key.strip() or key in docs or doc['entity']!=entity:raise ValueError('文档主体或标识无效')
        if day(doc['publishedAt'])>cutoff or not isinstance(doc.get('version'),str) or not doc['version'].strip() or not re.fullmatch('[0-9a-f]{64}',doc.get('sha256','')) or url.scheme!='https' or not url.hostname:raise ValueError('文档日期/版本/来源/摘要无效')
        docs[key]=doc
    def evidence(ref):
        if not isinstance(ref,dict) or ref.get('documentId') not in docs:raise ValueError('证据文档未登记')
        page=ref.get('physicalPage');quote=ref.get('quote')
        if isinstance(page,bool) or not isinstance(page,int) or page<1 or not isinstance(quote,str) or not quote.strip():raise ValueError('证据需物理页与引句')
        doc=docs[ref['documentId']];status='declared-not-original-verified'
        if doc.get('pdfPath'):status=cache.quote_status(doc['pdfPath'],doc['sha256'],page,quote)
        return dict(ref,source=doc['source'],sha256=doc['sha256'],version=doc['version'],publishedAt=doc['publishedAt'],pageVerification=status)
    rows={}
    for event in events:
        key=event['id'];kind=event['kind'];ref=evidence(event['evidence'])
        if not isinstance(key,str) or not key.strip() or key in rows or kind not in KINDS or event.get('entity')!=entity:raise ValueError('事件主体/类型/标识无效')
        for field in ['summary','researchQuestion','limitation']:
            if not isinstance(event.get(field),str) or not event[field].strip():raise ValueError('需明确研究问题和限制')
        period=event.get('reportPeriod');occurred=event.get('eventDate')
        if period is not None and day(period)>ref['publishedAt']:raise ValueError('披露期超出来源日期')
        if occurred is not None and day(occurred)>ref['publishedAt']:raise ValueError('事件日期超出来源日期')
        if kind=='audit-opinion' and (not isinstance(event.get('opinionText'),str) or not event['opinionText'].strip()):raise ValueError('审计意见须独立记录原意见文字')
        if kind=='audit-opinion' and event.get('auditScope') not in {'financial-statements','internal-control','other'}:raise ValueError('审计意见需区分财务报表与内控范围，不由审计师变更推断')
        if kind=='auditor-change' and not isinstance(event.get('auditorChange'),dict):raise ValueError('审计师变更需独立字段，不能代替审计意见')
        if kind=='auditor-change':
            change=event['auditorChange']
            if any(k not in change or (change[k] is not None and (not isinstance(change[k],str) or not change[k].strip())) for k in ['before','after']) or all(change[k] is None for k in ['before','after']):raise ValueError('审计师变更需前后机构，未知项留空，不能全部未知')
        rows[key]=dict(event,evidence=ref,interpretationStatus='declared-research-explanation-not-legal-verdict')
    links=[];seen=set()
    for link in relations:
        before,after=link['from'],link['to'];kind=link['type']
        if before not in rows or after not in rows or before==after or kind not in {'responds-to','corrects','restates','context-for'}:raise ValueError('关系无效')
        if (before,after,kind) in seen:raise ValueError('重复事件关系')
        seen.add((before,after,kind))
        if not isinstance(link.get('reason'),str) or not link['reason'].strip():raise ValueError('关联理由缺失')
        if kind=='responds-to' and (rows[before]['kind']!='inquiry' or rows[after]['kind']!='reply'):raise ValueError('回复关系类型不符')
        if kind in {'corrects','restates'} and rows[after]['kind']!=('correction' if kind=='corrects' else 'restatement'):raise ValueError('更正/重述关系类型不符')
        if kind!='context-for' and rows[before]['evidence']['publishedAt']>rows[after]['evidence']['publishedAt']:raise ValueError('关系披露顺序不符')
        links.append(dict(link,evidence=evidence(link['evidence']),status='explicit-link-not-causal-proof'))
    return {'toolVersion':'event-review-0.1.dev1','inputSchema':'event-evidence-ledger-v1','rulesVersion':'explicit-event-links-1','entity':entity,'asOf':cutoff,'sampleScope':spec.get('sampleType','declared-input-not-authenticated'),'events':list(rows.values()),'relations':links,'conclusion':f'整理了{len(rows)}项事件线索与{len(links)}条明确关联；应围绕所指问题继续核对，不凭标签定性。','limitations':['事件日期或报告期未知时保留空值，不拿披露日回填','审计意见与审计师变更分开；未提供的事件不表示不存在','不自动认定违规、因果或退市概率；关系不替换财报事实版本','原页引句匹配不等于事件全文或法律效力已经认证']}

def markdown(result):
    text='# 事件与研究问题\n\n'+result['conclusion']+'\n\n本次截止日：'+result['asOf']+'。样本范围：'+{'limited-public-evidence-not-full-case-certification':'有限公开回复案例，非完整事件核验','limited-public-correction-evidence':'有限公开更正案例，未配对原版和修订全文'}.get(result['sampleScope'],'声明输入，未自动认证')+'。\n\n'
    for event in result['events']:
        ref=event['evidence'];state={'quote-found-on-page':'指定原页找到引句，未完成全文核验','declared-not-original-verified':'仅声明页码与引句，未核本地原件','quote-not-found':'原页未找到引句','pdf-component-missing':'缺原页读取组件'}.get(ref['pageVerification'],'原页未确认');text+='原页状态：'+state+'\n\n';text+='## '+LABELS[event['kind']]+'：'+event['summary']+'\n\n研究上要问：'+event['researchQuestion']+'\n\n仍不能判断：'+event['limitation']+'\n\n来源：'+ref['source']+'，物理页'+str(ref['physicalPage'])+'，披露日'+ref['publishedAt']+'。\n\n'
    return text+'方法版本：'+result['toolVersion']+' / '+result['inputSchema']+' / '+result['rulesVersion']+'。\n\n## 限制\n\n'+'\n'.join('- '+x for x in result['limitations'])

def main():
    from cli_text import configure
    configure();p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',required=True,type=Path);p.add_argument('--format',choices=['json','markdown','html'],default='json');a=p.parse_args()
    if a.out.exists():raise FileExistsError('输出须为新文件')
    if a.input.stat().st_size>16*1024*1024:raise ValueError('输入过大')
    spec=json.loads(a.input.read_text('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant);result=review(spec)
    text=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False) if a.format=='json' else markdown(result)
    if a.format=='html':
        from research_brief_html import render
        text=render(text,'事件与研究问题')
        from event_html_controls import table
        controls=table(['事件','类型','披露日','研究问题'],[[e['summary'],LABELS[e['kind']],e['evidence']['publishedAt'],e['researchQuestion']] for e in result['events']])
        from html import escape
        hashes={name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in ['event_review.py','event_html_controls.py']}
        frozen='<details><summary>输入与方法摘要（分享前检查隐私）</summary><pre>'+escape(json.dumps({'input':spec,'methodSha256':hashes},ensure_ascii=False,indent=2,allow_nan=False))+'</pre></details>'
        text=text.replace('</body>',controls+frozen+'</body>')
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open('x',encoding='utf-8') as f:f.write(text)
    print(result['conclusion'])
if __name__=='__main__':main()
