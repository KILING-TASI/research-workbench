"""Explicit question/reply ledger; neither PDF acquisition nor reply-quality scoring."""
import argparse,datetime,hashlib,json,re
from pathlib import Path
from urllib.parse import urlparse
from collection_validation import unique_pairs,reject_constant,finite_json_float

def day(text):
    if not isinstance(text,str) or datetime.date.fromisoformat(text).isoformat()!=text:raise ValueError('日期须为YYYY-MM-DD')
    return text

def review(spec):
    if 'inputSchema' in spec and spec['inputSchema']!='inquiry-ledger-v1':raise ValueError('未知问询输入schema')
    if 'methodVersion' in spec and spec['methodVersion']!='explicit-association-2':raise ValueError('未知问询方法版本')
    if spec.get('originalInquiryStatus','not-established') not in ('not-established','not-obtained','declared-obtained-not-full-verified'):raise ValueError('原问询取得状态不能冒充全文验收')
    cutoff=day(spec['asOf']);entity=spec['entity']
    if not isinstance(entity,str) or not entity.strip():raise ValueError('主体缺失')
    documents=spec['documents'];questions=spec['questions'];responses=spec.get('responses',[])
    if not isinstance(documents,list) or not 1<=len(documents)<=100:raise ValueError('文档数量无效')
    if not isinstance(questions,list) or not 1<=len(questions)<=500 or not isinstance(responses,list) or len(responses)>1000:raise ValueError('问题或回复列表无效')
    from report_access.original_pages import InRunPDFPages
    docs={};pages=InRunPDFPages()
    for doc in documents:
        identity=doc['id']
        if not isinstance(identity,str) or not identity.strip() or identity in docs:raise ValueError('文档标识重复或缺失')
        if doc['entity']!=entity or day(doc['publishedAt'])>cutoff:raise ValueError('文档主体或截止日不符')
        if not isinstance(doc.get('version'),str) or not doc['version'].strip():raise ValueError('文档版本缺失')
        if not isinstance(doc.get('source'),str) or urlparse(doc['source']).scheme!='https' or not urlparse(doc['source']).hostname:raise ValueError('文档来源须为HTTPS')
        if not isinstance(doc.get('sha256'),str) or not re.fullmatch('[0-9a-f]{64}',doc['sha256']):raise ValueError('文档摘要缺失或无效')
        docs[identity]=doc
    def evidence(ref):
        if not isinstance(ref,dict) or ref.get('documentId') not in docs:raise ValueError('证据文档未登记')
        if isinstance(ref.get('physicalPage'),bool) or not isinstance(ref.get('physicalPage'),int) or ref['physicalPage']<1:raise ValueError('需明确PDF物理页')
        if not isinstance(ref.get('quote'),str) or not ref['quote'].strip():raise ValueError('原文引句缺失')
        doc=docs[ref['documentId']];status='declared-not-original-verified'
        if doc.get('pdfPath'):status=pages.quote_status(doc['pdfPath'],doc['sha256'],ref['physicalPage'],ref['quote'])
        return dict(ref,source=doc['source'],version=doc['version'],sha256=doc['sha256'],pageVerification=status)
    rows={}
    for q in questions:
        key=q['id']
        if not isinstance(key,str) or not key.strip() or key in rows:raise ValueError('问题编号重复或缺失')
        if not isinstance(q.get('text'),str) or not q['text'].strip():raise ValueError('问题正文缺失')
        origin=q.get('questionOrigin','declared-not-original-established')
        if origin not in ('original-inquiry','quoted-in-reply','declared-not-original-established'):raise ValueError('问题原文来源层级无效')
        rows[key]={'questionId':key,'question':q['text'],'questionOrigin':origin,'questionEvidence':evidence(q['evidence']),'replies':[]}
    ids=set()
    for response in responses:
        key=response['id'];targets=response['questionIds']
        if not isinstance(key,str) or not key.strip() or key in ids:raise ValueError('回复编号重复或缺失')
        ids.add(key)
        if not isinstance(targets,list) or not targets or len(set(targets))!=len(targets) or any(t not in rows for t in targets):raise ValueError('回复关联问题不合法')
        ref=evidence(response['evidence']);open_items=response.get('openItems',[])
        if not isinstance(open_items,list) or any(not isinstance(x,str) or not x.strip() for x in open_items):raise ValueError('未回答事项须为明确文字声明')
        for target in targets:
            before=docs[rows[target]['questionEvidence']['documentId']]['publishedAt']
            if docs[ref['documentId']]['publishedAt']<before:raise ValueError('回复披露早于关联问询')
            rows[target]['replies'].append({'responseId':key,'evidence':ref,'declaredOpenItems':open_items,'qualityJudgment':'not-assessed'})
    for row in rows.values():row.update(financialLinks=[],events=[])
    for name in ('financialLinks','events'):
        links=spec.get(name,[])
        if not isinstance(links,list) or len(links)>1000:raise ValueError('关联记录列表无效')
        for link in links:
            target=link.get('questionId')
            if target not in rows:raise ValueError('关联问题未登记')
            if not isinstance(link.get('reason'),str) or not link['reason'].strip():raise ValueError('关联理由缺失')
            ref=evidence(link['evidence'])
            if name=='financialLinks':
                for key in ('fieldId','metric','scope','basis','unit'):
                    if not isinstance(link.get(key),str) or not link[key].strip():raise ValueError('财报字段关联缺少口径：'+key)
                if link.get('entity')!=entity or day(link['period'])>docs[ref['documentId']]['publishedAt']:raise ValueError('财报主体或报告期不符')
            else:
                event_day=day(link['eventDate'])
                if event_day>docs[ref['documentId']]['publishedAt'] or event_day<docs[rows[target]['questionEvidence']['documentId']]['publishedAt']:raise ValueError('后续事件日期与问询/披露顺序不符')
            rows[target][name].append(dict(link,evidence=ref,associationStatus='declared-link-not-causal-proof'))
    missing=[key for key,row in rows.items() if not row['replies']]
    for row in rows.values():row['status']='reply-linked-not-quality-reviewed' if row['replies'] else 'matching-reply-not-obtained'
    original_date=spec.get('originalInquiryDate')
    if original_date is not None and day(original_date)>cutoff:raise ValueError('声明原问询日期超过截止日')
    headline=f'已整理{len(rows)}个选定问题，其中{len(missing)}个尚未取得匹配回复材料；关联成功不代表回复充分。'
    if spec.get('originalInquiryStatus')=='not-obtained':headline='本次只能做回复内转引对照，独立原函完整性与发函日期仍未知。'+headline
    return {'toolVersion':'inquiry-review-0.2.dev1','inputSchema':'inquiry-ledger-v1','rulesVersion':'explicit-association-2','entity':entity,'asOf':cutoff,'originalInquiryDate':original_date,'originalInquiryStatus':spec.get('originalInquiryStatus','not-established'),'questions':list(rows.values()),'missingReplyQuestionIds':missing,'conclusion':headline,'limitations':['问题拆分和匹配由输入明确声明，未自动读取PDF','页码与引句按各条证据状态说明；引句存在不等于回复充分','回复内转引问题不是独立原问询全文；回复披露日不回填原问询日期','缺回复不等于公司没有回复，不以问询推断造假或投资结论']}

def markdown(result):
    labels={'quote-found-on-page':'引句在指定原页找到','quote-not-found':'指定原页未找到引句，需复查','declared-not-original-verified':'仅声明页码，尚未核原页','pdf-component-missing':'原页读取组件缺失，尚未核对'}
    clean=lambda text:str(text).replace('|','／').replace(chr(10),' ')
    body='# 问询与回复：逐项研究底稿'+chr(10)*2+'> '+result['conclusion']+chr(10)*2+'本次主体：'+clean(result['entity'])+'；资料截止日：'+result['asOf']+'。'+chr(10)*2
    body+='独立原问询材料：'+('尚未取得，不能确认全文完整性' if result.get('originalInquiryStatus')=='not-obtained' else '状态按记录保留，未自动认证完整性')+'；原问询日期：'+str(result.get('originalInquiryDate') or '未知，不采用回复披露日代替')+'。'+chr(10)*2
    for row in result['questions']:
        body+='## 问题 '+clean(row['questionId'])+chr(10)*2+clean(row['question'])+chr(10)*2
        body+='问题依据层级：'+('公司回复内转引，未取得独立原函' if row.get('questionOrigin')=='quoted-in-reply' else '按输入声明的原件来源，完整性另核')+'。'+chr(10)*2
        evidence=row['questionEvidence'];body+='问题来源：'+evidence['source']+'，版本'+clean(evidence['version'])+'，PDF物理页'+str(evidence['physicalPage'])+'。'+chr(10)*2
        if not row['replies']:body+='尚未取得匹配回复材料，不表示公司没有回复。'+chr(10)*2
        for reply in row['replies']:
            ref=reply['evidence'];body+='关联回复：'+clean(reply['responseId'])+'；PDF物理页'+str(ref['physicalPage'])+'；原页引句状态：'+labels.get(ref['pageVerification'],'尚未核对')+'。关联不等于实质回答充分。'+chr(10)*2
            for item in reply['declaredOpenItems']:body+='- 输入声明仍需核对：'+clean(item)+chr(10)
        for field in row['financialLinks']:body+='- 关联财报字段：'+clean(field['metric'])+'，'+field['period']+'，'+clean(field['scope'])+' / '+clean(field['basis'])+'；理由：'+clean(field['reason'])+chr(10)
        for event in row['events']:body+='- 后续事件：'+event['eventDate']+'，'+clean(event['reason'])+'；关联不是因果证明。'+chr(10)
        body+=chr(10)
    body+='## 本次仍不能判断'+chr(10)*2+'本工具不评价回复质量，不给统一风险分数。原件中的问题完整性、公司解释与财报事实仍需逐项研究；不能据问询定性造假。'+chr(10)
    return body

def main():
    from cli_text import configure
    configure();p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',required=True,type=Path);p.add_argument('--format',choices=['json','markdown','html'],default='json');a=p.parse_args()
    if a.out.exists():raise FileExistsError('输出须为新文件')
    if a.input.stat().st_size>16*1024*1024:raise ValueError('输入过大')
    data=json.loads(a.input.read_text('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)
    result=review(data)
    text=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False) if a.format=='json' else markdown(result)
    if a.format=='html':
        from research_brief_html import render
        text=render(text,'问询与回复逐项研究')
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open('x',encoding='utf-8') as output:output.write(text)
    print(result['conclusion'])
if __name__=='__main__':main()
