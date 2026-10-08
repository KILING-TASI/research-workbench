"""Unified evidence export, conservative conflict explanations, portable research packages."""
import argparse, datetime as dt, hashlib, json, re, shutil, tempfile, uuid
from decimal import Decimal
from pathlib import Path
from collections import deque

def sha(blob): return hashlib.sha256(blob).hexdigest()
def canonical(obj): return json.dumps(obj, ensure_ascii=False, sort_keys=True, allow_nan=False).encode('utf-8')
def load(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def now(): return dt.datetime.now(dt.timezone.utc)
def timestamp(value):
    t=dt.datetime.fromisoformat(value)
    if t.tzinfo is None: raise ValueError('时间必须带时区')
    return t

def validate(nodes):
    if not isinstance(nodes,list) or any(not isinstance(n,dict) for n in nodes):raise ValueError('证据须为对象列表')
    ids={}
    for n in nodes:
        if not isinstance(n.get('id'),str) or not n['id'].strip() or n['id'] in ids: raise ValueError('证据ID缺失或重复')
        ids[n['id']]=n
        if n.get('kind') not in ['original','third-party','assumption','derived','missing']: raise ValueError('证据类型无效')
        if not n.get('subject') or not n.get('metric') or not n.get('verification'): raise ValueError('证据身份或核验状态缺失')
        if n['kind']=='original' and (not n.get('sourceUrl') or not n.get('documentSha256') or not n.get('publishedAt') or not (n.get('page') or n.get('locator'))): raise ValueError('原文证据来源/哈希/日期/定位缺失')
        if n.get('documentSha256') and not re.fullmatch('[0-9a-f]{64}',n['documentSha256']):raise ValueError('文件哈希格式无效')
        if n.get('page') is not None and (type(n['page']) is not int or n['page']<1):raise ValueError('页码须正整数')
        if n.get('publishedAt'):dt.date.fromisoformat(n['publishedAt'][:10])
        dependencies=n.get('dependsOn',[])
        if not isinstance(dependencies,list) or any(not isinstance(d,str) or not d.strip() for d in dependencies) or len(set(dependencies))!=len(dependencies):raise ValueError('证据依赖须为不重复的文本列表')
        if n['kind']=='derived' and (not dependencies or not n.get('formula')): raise ValueError('派生证据缺公式或依赖')
        if n['kind']=='missing' and n.get('value') is not None: raise ValueError('缺失证据不能有值')
    parents={key:[] for key in ids};pending={key:len(n.get('dependsOn',[])) for key,n in ids.items()}
    for key,n in ids.items():
        for dependency in n.get('dependsOn',[]):
            if dependency not in ids:raise ValueError('不存在的依赖:'+dependency)
            parents[dependency].append(key)
    ready=deque(key for key,count in pending.items() if count==0);done=0
    while ready:
        key=ready.popleft();done+=1
        for parent in parents[key]:
            pending[parent]-=1
            if pending[parent]==0:ready.append(parent)
    if done!=len(ids):raise ValueError('证据依赖循环')
    return nodes

def export(spec):
    nodes=[];attachments=[]
    if spec.get('factsStore'):
        from issuance_facts import view
        data=view({'code':spec['code'],'asOf':spec['asOf']},Path(spec['factsStore']))
        for r in data['versions']:
            attachments.append({'path':r['documentPath'],'sha256':r['documentSha256'],'role':'original-pdf'})
            if r.get('metadataArchivePath'):attachments.append({'path':r['metadataArchivePath'],'sha256':r['publicationEvidence']['metadataSha256'],'role':'publication-metadata'})
            for metric,f in r['facts'].items():
                nodes.append({'id':r['versionHash']+':'+metric,'subject':spec['code'],'metric':metric,'kind':'original',
                    **f,'period':None,'locator':{'label':f['label']},'retrievedAt':r['recordedAt'],'asOf':spec['asOf'],
                    'version':r['versionHash'],'supersedes':r.get('supersedes'),'dependsOn':[],
                    'limitation':'数值摘录匹配；字段语义与首次公开时间仍需核验'})
    if spec.get('companyResult'):
        path=Path(spec['companyResult']);data=load(path)
        attachments.append({'path':str(path.resolve()),'sha256':sha(path.read_bytes()),'role':'company-result'})
        for d in data.get('documents',{}).values():attachments.append({'path':d['path'],'sha256':d['sha256'],'role':'company-original'})
        for key,e in data.get('evidence',{}).items():
            nodes.append({'id':'company:'+key,'subject':data['code'],'metric':e.get('label',e.get('topic')),'kind':'original',
                'value':e.get('value'),'unit':e.get('unit'),'basis':'supplied-excerpt-mapping','period':e.get('period'),
                'sourceUrl':e['sourceUrl'],'documentSha256':e['documentSha256'],'page':e['page'],
                'locator':{k:e[k] for k in ['tableIndex','rowIndex','column','headerRow','headerColumn'] if k in e},
                'excerpt':e.get('text'),'publishedAt':e['publishedAt'],'publicationVerification':'caller-declared',
                'verification':e['verification'],'dependsOn':[],'limitation':'摘录核验等级沿用原输出，不能升级'})
    nodes.extend(spec.get('nodes',[]));validate(nodes)
    return {'type':'bjx-evidence-interface','schemaVersion':1,'nodes':nodes,'attachments':attachments,
        'limitations':['当前适配发行事实及公司原文证据；其他计算节点须显式提供依赖与公式','统一格式不提升核验等级，不认证来源URL与线上文件一致']}

def normalized(n):
    try:
        v=Decimal(str(n.get('value')))
        return str(v.normalize()) if v.is_finite() else str(n.get('value'))
    except Exception:return str(n.get('value'))

def conflicts(data):
    nodes=validate(data['nodes']);groups={};out=[]
    for n in nodes:groups.setdefault((n['subject'],n['metric']),[]).append(n)
    for (subject,metric),items in groups.items():
        if len(items)<2:continue
        replaced={n.get('supersedes') for n in items if n.get('supersedes')}
        active=[n for n in items if n.get('version') not in replaced]
        reasons=[]
        for field,label in [('unit','unit-difference'),('period','period-difference'),('basis','scope-or-basis-difference')]:
            if len({str(n.get(field)) for n in active})>1:reasons.append(label)
        if len(active)<len(items):reasons.append('declared-supersession')
        if len({n.get('version') for n in items if n.get('version')})>1:reasons.append('different-document-versions')
        sig={(normalized(n),n.get('unit'),n.get('period'),n.get('basis')) for n in active}
        unresolved=len(sig)>1 or not active or any(n['kind']=='missing' for n in active)
        if unresolved and not reasons:reasons.append('unexplained-value-conflict')
        out.append({'subject':subject,'metric':metric,'candidateIds':[n['id'] for n in items],
            'activeIds':[n['id'] for n in active],'reasons':reasons or ['consistent-values'],
            'status':'unresolved' if unresolved else 'consistent-under-declared-metadata',
            'resolvedValue':None if unresolved else active[-1].get('value'),
            'requiredReview':'核对原文的范围、期间、单位、更正关系；不按多数或最新日期自动裁决'})
    return {'type':'bjx-field-conflict-explanations','groups':out,'automaticFactAdjudication':False}

def package(spec,workspace):
    mode=spec.get('mode','research');recorded=now()
    if mode not in ['research','historical-replay','predecision']:raise ValueError('快照模式无效')
    cutoff=timestamp(spec['decisionCutoff']) if spec.get('decisionCutoff') else None
    if mode=='predecision' and (cutoff is None or recorded>=cutoff):raise ValueError('截止已过或缺失，不能创建事前快照')
    evidence=export(spec['evidence']);report=conflicts(evidence)
    declared=spec.get('dependencies',[])
    if not isinstance(declared,list) or not declared:raise ValueError('必须声明研究输入、规则及计算结果依赖清单')
    entries=evidence['attachments']+declared
    roles={e.get('role') for e in entries}
    missingRoles=sorted({'research-input','rule','calculation-result'}-roles)
    if missingRoles:raise ValueError('缺少快照依赖角色:'+','.join(missingRoles))
    checked=[];blobs={}
    for item in entries:
        p=Path(item['path']);blob=p.read_bytes()
        if len(blob)>100*1024*1024:raise ValueError('文件超过100MiB')
        h=sha(blob)
        if item.get('sha256') and item['sha256']!=h:raise ValueError('依赖文件哈希不符')
        available=item.get('availableAt') or spec.get('availabilityBySha256',{}).get(h)
        if mode=='predecision' and (not available or timestamp(available)>cutoff or timestamp(available)>recorded):raise ValueError('事前包每项依赖需声明可得时间且不得在未来')
        checked.append({'name':p.name,'role':item['role'],'sha256':h,'archive':'files/'+h,'availableAt':available,
            'availabilityVerification':'caller-declared' if available else 'unknown'})
        blobs[h]=blob
    hashes={e['sha256'] for e in checked}
    if any(n['kind']=='original' and n['documentSha256'] not in hashes for n in evidence['nodes']):raise ValueError('证据引用的原文件未打包')
    root=Path(workspace)/'research-data'/'bjx-research-packages';root.mkdir(parents=True,exist_ok=True)
    folder=root/uuid.uuid4().hex
    with tempfile.TemporaryDirectory(dir=root) as temp:
        staging=Path(temp);(staging/'files').mkdir()
        for h,b in blobs.items():(staging/'files'/h).write_bytes(b)
        for name,obj in [('evidence.json',evidence),('conflicts.json',report),('spec.json',spec)]:
            (staging/name).write_bytes(canonical(obj))
        manifest={'type':'bjx-research-snapshot-package','schemaVersion':1,'mode':mode,'recordedAt':recorded.isoformat(),
            'decisionCutoff':spec.get('decisionCutoff'),'dependencies':checked,
            'files':{str(p.relative_to(staging)).replace('\\','/'):sha(p.read_bytes()) for p in staging.rglob('*') if p.is_file()},
            'completeness':'declared-dependency-closure-checked-not-all-research-certified',
            'eligibleForModelImprovement':False,'limitations':['时间与可得性是本地记录及用户声明，无外部签名','仅检查声明依赖完整性，不能证明研究无遗漏','历史回放不能升级成真实事前冻结样本']}
        manifest['manifestHash']=sha(canonical(manifest));(staging/'manifest.json').write_bytes(canonical(manifest))
        shutil.copytree(staging,folder)
    return {'packagePath':str(folder.resolve()),**manifest}

def verify(folder):
    root=Path(folder).resolve();m=load(root/'manifest.json');h=m.pop('manifestHash')
    if sha(canonical(m))!=h:raise ValueError('清单被修改')
    expected=set(m['files'])|{'manifest.json'}
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if expected!=actual:raise ValueError('包内文件缺失或出现未登记文件')
    for name,digest in m['files'].items():
        p=(root/name).resolve()
        if not p.is_relative_to(root) or sha(p.read_bytes())!=digest:raise ValueError('包内路径越界或文件被修改')
    return {'verified':True,'fileCount':len(m['files']),'mode':m['mode'],'eligibleForModelImprovement':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['export','conflicts','package','verify']);p.add_argument('input',type=Path);p.add_argument('--workspace',type=Path,default=Path.cwd());p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():raise ValueError('输出已存在')
    s=load(a.input) if a.command!='verify' else None
    r=export(s) if a.command=='export' else conflicts(s) if a.command=='conflicts' else package(s,a.workspace) if a.command=='package' else verify(a.input)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open('x',encoding='utf-8') as f:json.dump(r,f,ensure_ascii=False,indent=2,allow_nan=False)
if __name__=='__main__':main()
