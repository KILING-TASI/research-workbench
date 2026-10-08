"""Research snapshot, transparent metric screening and comparison-pool handoff."""
import argparse, copy, hashlib, json, math, re
from pathlib import Path
from collection_validation import unique_pairs,reject_constant,finite_json_float

NOTICE = '仅作客观研究，不构成投资建议。本金可能亏损，历史统计与情景测算不代表未来。'
SKIP = {'inputSnapshot','acceptance','inputAudit','createdAt','engineVersion','type','inputSha256','calendarComplete','riskNotice'}

def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)

def finite(v):
    return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)

def screen(spec):
    result=spec['result']; rows=result.get('comparisons')
    if rows is None: rows=result.get('assets')
    if not isinstance(rows,list) or not rows or len(rows)>500: raise ValueError('需最多500个标的指标')
    rules=spec.get('conditions'); accepted=[]; excluded=[]; unknown=[]; seen=set()
    if not isinstance(rules,list) or not rules: raise ValueError('筛选条件不能为空')
    ops={'lt':lambda a,b:a<b,'le':lambda a,b:a<=b,'gt':lambda a,b:a>b,'ge':lambda a,b:a>=b,'eq':lambda a,b:a==b}
    for rule in rules:
        if rule.get('op') not in ops or not finite(rule.get('value')) or rule.get('metric') not in ['maximumDrawdownPct','annualVolatilityPct','Sharpe','Sortino','Calmar','CAGRPct']: raise ValueError('指标、比较符或阈值无效，百分数须百分点')
    for row in rows:
        code=row.get('code')
        if not isinstance(code,str) or not code or code in seen: raise ValueError('标的代码须非空唯一')
        seen.add(code); reasons=[]; missing=[]
        for rule in rules:
            value=row.get('metrics',row).get(rule['metric'])
            if isinstance(value,dict): value=value.get('value')
            if not finite(value): missing.append(rule['metric'])
            elif not ops[rule['op']](value,rule['value']): reasons.append({'metric':rule['metric'],'value':value,'op':rule['op'],'threshold':rule['value']})
        item={'code':code,'failedConditions':reasons,'missingMetrics':missing}
        if reasons: excluded.append(item)
        elif missing: unknown.append(item)
        else: accepted.append(code)
    pool=None; history=spec.get('historyInput')
    if history is not None:
        pool=copy.deepcopy(history); pool['assets']=[a for a in pool.get('assets',[]) if a['code'] in accepted]
        if {a['code'] for a in pool['assets']}!=set(accepted): raise ValueError('入池历史缺标的，不能只传代码假装可比较')
        for asset in pool['assets']: asset['weight']=1/len(accepted)
        if not accepted: pool=None
    return {'type':'metric-screen','conditions':rules,'selectedCodes':accepted,'excluded':excluded,'unknown':unknown,'comparisonInput':pool,'riskNotice':NOTICE,'limitations':['筛选仅基于输入历史指标，满足条件不等于产品优质或未来满足条件','缺指标不视为通过；无历史时仅生成代码池','比较池内等权只是统计计算输入，不是配置建议']}

def snapshot(result,title,notes=None):
    if not isinstance(result,dict) or not isinstance(title,str) or not title.strip(): raise ValueError('需结果对象和标题')
    identity={}
    if 'subjectCodes' in result:
        codes=result['subjectCodes']
        if not isinstance(codes,list) or not codes or any(not isinstance(c,str) or not c.strip() for c in codes) or len(codes)!=len(set(codes)):raise ValueError('快照主体列表无效')
        identity['subjectCodes']=copy.deepcopy(codes)
    if 'code' in result:
        if not isinstance(result['code'],str) or not result['code'].strip():raise ValueError('快照主体代码无效')
        if identity and result['code'] not in identity['subjectCodes']:raise ValueError('快照主体声明冲突')
        identity['code']=result['code']
    rows=[]; sources=[]; limitations=[];embedded_notes=[]
    def walk(v,path='',depth=0):
        if depth>20: raise ValueError('结果层级过深')
        if isinstance(v,dict):
            for k,x in v.items():
                if k in SKIP or k in ['seen','history','steps','daily','evidenceFile','sourceRecord','executionLog','importVersions']: continue
                if k in ['sourceUrl','url','source'] and isinstance(x,str) and re.match('https?://',x):
                    sources.append([path or '研究结果',x]); continue
                if k in ['limitations','note','notes']:
                    if k=='notes' and isinstance(x,list) and any(isinstance(y,dict) for y in x):
                        for y in x:
                            if not isinstance(y,dict) or not isinstance(y.get('text'),str) or not y['text'].strip():raise ValueError('结构化笔记须提供非空正文')
                            for ref in ['evidenceIds','conclusionIds']:
                                ids=y.get(ref,[])
                                if not isinstance(ids,list) or any(not isinstance(i,str) or not i.strip() for i in ids):raise ValueError('笔记关联须为文本列表')
                            embedded_notes.append(y)
                    elif isinstance(x,list): limitations.extend(str(y) for y in x)
                    elif isinstance(x,str): limitations.append(x)
                    continue
                walk(x, (path+'.' if path else '')+k,depth+1)
        elif isinstance(v,list):
            for i,x in enumerate(v): walk(x,path+'['+str(i+1)+']',depth+1)
        else:
            if isinstance(v,float) and not math.isfinite(v): raise ValueError('结果包含非有限值')
            rows.append([path,v if v is not None else '待核验'])
            if len(rows)>5000: raise ValueError('简报最多5000项，需缩小范围')
    walk(result)
    # Source provenance can live only in the saved input; preserve URLs without displaying file paths.
    def urls(v,path='输入依据'):
        if isinstance(v,dict):
            label=v.get('code') or v.get('id') or path
            for k,x in v.items():
                if k in ['sourceUrl','url'] and isinstance(x,str) and re.match('https?://',x): sources.append([str(label),x])
                elif k not in ['history','seen']: urls(x,str(label))
        elif isinstance(v,list):
            for x in v: urls(x,path)
    urls(result)
    sources=list(dict.fromkeys(tuple(x) for x in sources))
    labels={'alignment':'比较区间','start':'起始日','end':'截止日','observations':'观察数','removed':'日期对齐','removedObservations':'未纳入观察数','code':'代码','comparisons':'标的','metrics':'指标','CAGRPct':'年化收益率（时间加权，%）','annualVolatilityPct':'年化波动（%）','maximumDrawdownPct':'最大回撤（%）','Sharpe':'夏普比率','Sortino':'索提诺比率','Calmar':'卡玛比率','value':'数值','poolMedian':'比较池中位数','relation':'单项比较','definition':'含义','correlation':'历史相关性','codes':'代码顺序','matrix':'矩阵','benchmark':'参照基准','events':'事件'}
    def label(path):
        return '.'.join(re.sub(r'^[A-Za-z][A-Za-z0-9]*',lambda m:labels.get(m.group(),m.group()),part) for part in path.split('.'))
    relations={'above-pool-on-this-metric':'按该指标方向相对有利，不代表总体优劣','below-pool-on-this-metric':'按该指标方向相对不利，不代表总体优劣','equal':'相同','unknown':'待核验'}
    rows=[[label(k),relations.get(v,v) if isinstance(v,str) else v] for k,v in rows]
    note_rows=[]
    if notes is not None and not isinstance(notes,list):raise ValueError('用户笔记须为列表')
    for note in [*embedded_notes,*(notes or [])]:
        if not isinstance(note,dict) or note.get('kind')!='user-note' or not isinstance(note.get('text'),str) or not note['text'].strip(): raise ValueError('用户笔记须单独标识并提供非空正文')
        for ref in ['evidenceIds','conclusionIds']:
            ids=note.get(ref,[])
            if not isinstance(ids,list) or any(not isinstance(i,str) or not i.strip() for i in ids):raise ValueError('笔记关联须为文本列表')
        refs=[*note.get('evidenceIds',[]),*note.get('conclusionIds',[])]
        note_rows.append([note.get('at',''),note['text']+('；关联记录：'+'、'.join(refs) if refs else '')])
    return {'type':'research-result-snapshot',**identity,'title':title,'notice':NOTICE,'rows':rows,'sources':[list(x) for x in sources], 'limitations':list(dict.fromkeys(limitations)), 'userNotes':note_rows,'sourceHash':hashlib.sha256(json.dumps(result,ensure_ascii=False,sort_keys=True,allow_nan=False).encode()).hexdigest()}

def task_notes(task,result):
    notes=task.get('notes',[])
    if not notes:return []
    def subjects(value):
        codes=value.get('subjectCodes',[])
        if not isinstance(codes,list) or any(not isinstance(c,str) or not c.strip() for c in codes):raise ValueError('任务主体列表无效')
        if 'code' in value:
            code=value['code']
            if not isinstance(code,str) or not code.strip():raise ValueError('任务主体代码无效')
            codes=[*codes,code]
        return set(codes)
    target=subjects(result);source=task.get('sourceRecord',{}).get('snapshot',{})
    if not isinstance(source,dict):raise ValueError('任务首次快照无效')
    if target and subjects(source)!=target:raise ValueError('任务笔记主体与导出结果不一致或尚未确认')
    return notes

def markdown(d):
    escape=lambda x:str(x).replace('|',chr(92)+'|').replace('\r',' ').replace('\n','<br>')
    text=['# '+d['title'],'',d['notice'],'','| 项目 | 结果 |','| --- | --- |']
    text += ['| '+escape(k)+' | '+escape(v)+' |' for k,v in d['rows']]
    text += ['','## 资料来源','']+[ '- '+escape(label)+'：'+url for label,url in d['sources']]
    if not d['sources']: text.append('本结果未提供来源链接，需补充核对。')
    text += ['','## 假设与限制','']+['- '+escape(x) for x in d['limitations']]
    if d['userNotes']: text += ['','## 用户笔记','']+['- '+escape(t)+'：'+escape(x) for t,x in d['userNotes']]
    return '\n'.join(text)+'\n'

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['screen','snapshot']);p.add_argument('input',type=Path);p.add_argument('--out-dir',type=Path,required=True);a=p.parse_args()
    spec=read(a.input)
    if a.command=='screen': result=screen(spec)
    else:
        notes=spec.get('notes',[])
        if spec.get('taskId'):
            from research_tasks import read as task_read, task_path
            task=task_read(task_path(Path(spec['taskStore']),spec['taskId']))
            notes=task_notes(task,spec['result'])+notes
        result=snapshot(spec['result'],spec['title'],notes)
    a.out_dir.mkdir(parents=True,exist_ok=False)
    (a.out_dir/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    if a.command=='screen' and result['comparisonInput'] is not None: (a.out_dir/'comparison-input.json').write_text(json.dumps(result['comparisonInput'],ensure_ascii=False,indent=2),encoding='utf-8')
    if a.command=='snapshot': (a.out_dir/'report.md').write_text(markdown(result),encoding='utf-8')
    print(json.dumps({'output':str(a.out_dir),'type':a.command}))
if __name__=='__main__': main()
