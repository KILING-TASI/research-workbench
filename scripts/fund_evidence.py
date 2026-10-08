"""Validate evidence bindings and preserve auditable research packages; no ratings."""
import argparse, hashlib, json, math
from pathlib import Path
from datetime import date
from collections import deque
from collection_validation import day,unique_pairs,reject_constant,finite_json_float
from research_library import url as validate_source

def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,allow_nan=False).encode()).hexdigest()
def build(s):
    if not isinstance(s,dict) or not isinstance(s.get('subjectCodes'),list) or any(not isinstance(c,str) or not c.strip() for c in s['subjectCodes']):raise ValueError('研究主体须为非空文本数组')
    if any(not isinstance(s.get(k,[]),list) or any(not isinstance(x,dict) for x in s.get(k,[])) for k in ['evidence','conclusions','notes']):raise ValueError('证据、结论及笔记须为对象数组')
    codes=s['subjectCodes'];asof=s['asOf'];day(asof)
    if not codes or len(codes)!=len(set(codes)):raise ValueError('研究主体须唯一')
    records=s['evidence'];ids=set();checked=[]
    for r in records:
        if not isinstance(r.get('inputEvidenceIds',[]),list) or any(not isinstance(i,str) or not i for i in r.get('inputEvidenceIds',[])):raise ValueError('计算输入证据ID须为文本数组')
        if len(r.get('inputEvidenceIds',[]))!=len(set(r.get('inputEvidenceIds',[]))):raise ValueError('计算输入证据ID重复')
        if not isinstance(r.get('id'),str) or not r.get('id','').strip() or r['id'] in ids or r.get('code') not in codes:raise ValueError('证据ID重复或主体不符')
        ids.add(r['id'])
        if r.get('status') not in ['original-disclosed','derived','assumption','missing','conflict']:raise ValueError('证据状态无效')
        if r['status'] not in ['missing','conflict'] and r.get('value') is None:raise ValueError('有值状态缺少数值/文本')
        if r['status']=='missing' and r.get('value') is not None:raise ValueError('缺失不能填值')
        if r['status']=='conflict' and (not isinstance(r.get('alternatives'),list) or len(r['alternatives'])<2 or any(not isinstance(x,dict) for x in r['alternatives'])):raise ValueError('冲突需同时保留至少两个候选')
        for k in ['disclosedAt','observedAt']:
            if r.get(k) is not None:day(r[k])
            if r.get(k) and date.fromisoformat(r[k])>date.fromisoformat(asof):raise ValueError('证据晚于截止日')
        if r.get('disclosedAt') and r.get('observedAt') and r['observedAt']<r['disclosedAt']:raise ValueError('证据取得日不能早于披露日')
        if r['status']=='original-disclosed':
            validate_source(r.get('sourceUrl'))
            if not r.get('disclosedAt') or not isinstance(r.get('locator'),str) or not r['locator'].strip():raise ValueError('原文需URL、披露日期与定位')
            verification='source-declared-not-original-checked'
            if r.get('quote') is not None and (not isinstance(r['quote'],str) or not r['quote'].strip()):raise ValueError('原文摘录须为非空文本')
            if r.get('pdf'):
                raw=Path(r['pdf']).read_bytes()
                if hashlib.sha256(raw).hexdigest()!=r.get('fileSha256'):raise ValueError('原文文件哈希不符')
                import pdfplumber
                with pdfplumber.open(r['pdf']) as doc:
                    page=r.get('page');bbox=r.get('bbox')
                    if isinstance(page,bool) or not isinstance(page,int) or not 1<=page<=len(doc.pages):raise ValueError('页码超出原文')
                    verification='hash-and-page-checked-only'
                    if bbox is not None:
                        if not isinstance(bbox,(list,tuple)) or len(bbox)!=4 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in bbox):raise ValueError('坐标无效')
                        x0,y0,x1,y1=bbox;p=doc.pages[page-1]
                        if not 0<=x0<x1<=p.width or not 0<=y0<y1<=p.height:raise ValueError('坐标超出页边界')
                        extracted=p.crop(bbox).extract_text() or ''
                        if r.get('quote') and ''.join(r['quote'].split()) not in ''.join(extracted.split()):raise ValueError('证据摘录与坐标区域不符')
                        if r.get('quote'):verification='quote-found-in-declared-region'
                    elif r.get('quote'):
                        extracted=doc.pages[page-1].extract_text() or ''
                        if ''.join(r['quote'].split()) not in ''.join(extracted.split()):raise ValueError('证据摘录与原文页不符')
                        verification='quote-found-on-declared-page'
            r={**r,'originalVerification':{'status':verification,'scope':'定位与文件检查，不认证数值定义、真实性或全部原文'}}
        if r['status']=='derived' and (not r.get('formula') or not r.get('inputEvidenceIds') or not isinstance(r.get('parameters'),dict) or not r['parameters']):raise ValueError('计算值需公式、输入证据与参数')
        checked.append(r)
    for r in checked:
        if any(i not in ids for i in r.get('inputEvidenceIds',[])):raise ValueError('计算引用未知证据')
    # Resolve each DAG node once, carrying uncertainty through every dependency.
    by_id={r['id']:r for r in checked};graph={i:set(r.get('inputEvidenceIds',[])) for i,r in by_id.items()}
    parents={i:[] for i in ids};pending={i:len(children) for i,children in graph.items()}
    statuses_by_id={i:{by_id[i]['status']} for i in ids}
    for parent,children in graph.items():
        for child in children:parents[child].append(parent)
    ready=deque(i for i in ids if pending[i]==0);resolved=0
    while ready:
        child=ready.popleft();resolved+=1
        for parent in parents[child]:
            statuses_by_id[parent].update(statuses_by_id[child]);pending[parent]-=1
            if pending[parent]==0:ready.append(parent)
    if resolved!=len(ids):raise ValueError('计算证据循环引用')
    conclusions=[]
    for c in s.get('conclusions',[]):
        if not isinstance(c.get('evidenceIds'),list) or any(not isinstance(i,str) or not i.strip() for i in c['evidenceIds']) or len(c['evidenceIds'])!=len(set(c['evidenceIds'])):raise ValueError('结论证据ID须为不重复的文本数组')
        if any(not isinstance(c.get(k),str) or not c[k].strip() for k in ['id','text']):raise ValueError('结论身份及正文须为非空文本')
        if not c.get('id') or not c.get('text') or not c.get('evidenceIds') or any(i not in ids for i in c['evidenceIds']):raise ValueError('结论须绑定已有证据')
        if c.get('grade') not in ['disclosed-fact','calculated','estimate','withheld']:raise ValueError('结论分级无效')
        statuses=set().union(*(statuses_by_id[i] for i in c['evidenceIds']))
        if c['grade'] in ['disclosed-fact','calculated'] and statuses & {'assumption','missing','conflict'}:raise ValueError('缺失、冲突或假设不能标确定结论')
        if c['grade']=='disclosed-fact' and statuses!={'original-disclosed'}:raise ValueError('原文事实不能混入推算')
        if not isinstance(c.get('limitations'),list) or not c['limitations'] or any(not isinstance(v,str) or not v.strip() for v in c['limitations']):raise ValueError('逐结论局限须为非空文本列表')
        coverage=c.get('coverage')
        if coverage is not None:
            if not isinstance(coverage,dict):raise ValueError('覆盖率口径须为对象')
            known,total=coverage.get('known'),coverage.get('total')
            if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in [known,total]) or not 0<=known<=total or total<=0 or not isinstance(coverage.get('basis'),str) or not coverage['basis'].strip():raise ValueError('覆盖分母或口径无效')
            c={**c,'coverage':{**coverage,'pct':known/total*100,'meaning':'数据覆盖率，不是准确率/置信度'}}
        conclusions.append(c)
    cids=[c['id'] for c in conclusions]
    if len(cids)!=len(set(cids)):raise ValueError('结论ID重复')
    notes=[]
    for n in s.get('notes',[]):
        for key in ['evidenceIds','conclusionIds']:
            refs=n.get(key,[])
            if not isinstance(refs,list) or any(not isinstance(i,str) or not i.strip() for i in refs) or len(refs)!=len(set(refs)):raise ValueError('笔记引用须为不重复的文本数组')
        targets=n.get('evidenceIds',[])+n.get('conclusionIds',[])
        if not isinstance(n.get('text'),str) or not n['text'].strip() or not targets or any(i not in ids for i in n.get('evidenceIds',[])) or any(i not in cids for i in n.get('conclusionIds',[])):raise ValueError('笔记须为非空文本并绑定证据或结论')
        notes.append({**n,'kind':'user-note'})
    canonical={'subjectCodes':codes,'asOf':asof,'methodology':s.get('methodology',{}),'evidence':checked,'conclusions':conclusions,'notes':notes}
    return {'type':'fund-evidence-package',**canonical,'packageVersion':digest(canonical),
            'limitations':['定位/哈希检查不证明文档内容真实，不直接判定财务造假',
                            '计算路径记录可支持复算，不代表本模块已重新执行每个公式',
                            '完整报告日持仓不等于逐日精确归因；覆盖率不是统计置信度']}

def compare(s):
    if not isinstance(s,dict) or any(not isinstance(s.get(k),dict) for k in ['before','after']):raise ValueError('版本比较须提供前后证据包对象')
    a,b=s['before'],s['after'];stored_before=a.get('packageVersion');stored_after=b.get('packageVersion')
    if a.get('type')!='fund-evidence-package' or b.get('type')!='fund-evidence-package' or a['subjectCodes']!=b['subjectCodes']:raise ValueError('需同主体证据包')
    # Revalidate packages rather than trusting their stored status flags.
    a=build(a);b=build(b);rows=[]
    aa={r['id']:r for r in a['evidence']};bb={r['id']:r for r in b['evidence']}
    for i in sorted(aa.keys()|bb.keys()):
        old,new=aa.get(i),bb.get(i)
        fields=[k for k in set(old or {})|set(new or {}) if (old or {}).get(k)!=(new or {}).get(k)]
        if fields:rows.append({'evidenceId':i,'changedFields':sorted(fields),'before':old,'after':new})
    return {'type':'fund-evidence-version-diff','subjectCodes':a['subjectCodes'],'beforeVersion':a['packageVersion'],'afterVersion':b['packageVersion'],'beforeStoredVersion':stored_before,'afterStoredVersion':stored_after,
            'evidenceChanges':rows,'methodologyChanged':a['methodology']!=b['methodology'],
            'conclusionsChanged':a['conclusions']!=b['conclusions'],'notesChanged':a['notes']!=b['notes'],
            'limitations':['列明文档、解析与口径变化，不自动推断经济事实或因果变化；不覆盖旧版本','前后内容按当前规则重新校验，原存版本标识另列，不假称旧包由当前方法生成']}

def read_input(path):
    path=Path(path).resolve()
    spec=json.loads(path.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)
    packages=[spec]
    if isinstance(spec,dict):packages += [spec[k] for k in ['before','after'] if isinstance(spec.get(k),dict)]
    for package in packages:
        if not isinstance(package,dict) or not isinstance(package.get('evidence'),list):continue
        for record in package['evidence']:
            if not isinstance(record,dict) or record.get('pdf') is None:continue
            if not isinstance(record['pdf'],str) or not record['pdf'].strip():raise ValueError('原文PDF路径须为非空文本')
            p=Path(record['pdf']);record['pdf']=str(p if p.is_absolute() else (path.parent/p).resolve())
    return spec

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['build','compare']);p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    result={'build':build,'compare':compare}[a.command](read_input(a.input))
    serialized=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open('x',encoding='utf8') as f:f.write(serialized)
