"""On-demand pool, archive, disclosure search and snapshot attribution."""
import argparse, copy, datetime as dt, hashlib, json, math, re, uuid
from pathlib import Path
from urllib.parse import urlsplit
from collection_validation import unique_pairs,reject_constant,finite_json_float

NOTICE='仅作客观研究，不构成投资建议；历史统计和假设结果不代表未来收益。'

def number(v,name,minvalue=None):
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or (minvalue is not None and v<minvalue): raise ValueError(name+'数值无效')
    return v

def day(v):
    if not isinstance(v,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',v): raise ValueError('日期须YYYY-MM-DD')
    return dt.date.fromisoformat(v)

def url(v):
    if not isinstance(v,str) or re.search(r'[\s\x00-\x1f\x7f]',v):raise ValueError('来源URL格式无效')
    parts=urlsplit(v)
    if parts.scheme not in ('http','https') or not parts.hostname or parts.username is not None or parts.password is not None:raise ValueError('来源URL须为无凭据的HTTP或HTTPS地址')
    if parts.port not in (None,80,443):raise ValueError('来源URL端口无效')
    return v

def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)
def dump(p,d):
    text=json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:f.write(text)
def stamp(): return dt.datetime.now(dt.timezone.utc).isoformat()
def key(v): return hashlib.sha256(v.encode('utf-8')).hexdigest()
def code(v):
    if not isinstance(v,str) or not re.fullmatch(r'\d{6}',v): raise ValueError('基金代码须六位字符串')
    return v

# Effects in percentage points: weights are fractions and returns are percentages.
def brinson(s):
    if not isinstance(s,dict):raise ValueError('归因输入须为对象')
    if not isinstance(s.get('industryVersion'),str) or not s['industryVersion'].strip():raise ValueError('行业分类版本未明确，不能计算归因')
    start,end,cutoff=day(s['start']),day(s['end']),day(s['asOf'])
    if not start<end<=cutoff or day(s['weightDate'])>start: raise ValueError('权重必须来自区间开始前快照，不能用期末权重解释之前收益')
    published=s.get('weightPublishedAt')
    if published is None:
        timing={'status':'publication-date-missing','publishedAt':None,'note':'持仓报告发布日期未提供，不能证明区间开始前已可取得。'}
    else:
        publication=day(published)
        if publication>cutoff or publication<day(s['weightDate']):raise ValueError('持仓披露日期晚于研究截止日或早于快照日期')
        status='declared-before-period-not-externally-verified' if publication<start else 'same-day-timing-unconfirmed' if publication==start else 'retrospective-only'
        notes={'declared-before-period-not-externally-verified':'登记披露日早于收益区间，发布日期真实性仍需原文核验。','same-day-timing-unconfirmed':'报告与区间起点同日，缺少时刻，不能证明起点前可取得。','retrospective-only':'报告在收益区间开始后披露，只能用于事后解释，不能作为期初可用策略输入。'}
        timing={'status':status,'publishedAt':published,'note':notes[status]}
    if s.get('basis') not in ['disclosed-snapshot-estimate','period-start-holdings'] or not s.get('industrySystem') or s.get('returnBasis')!='total-return': raise ValueError('需权重依据、行业分类与总收益口径')
    rows=s['sectors']
    if not isinstance(rows,list) or any(not isinstance(r,dict) for r in rows):raise ValueError('行业归因条目须为对象列表')
    if any(r.get('industryVersion',s['industryVersion'])!=s['industryVersion'] for r in rows):raise ValueError('行业分类版本冲突')
    if not rows or len(rows)>100 or len({r['industry'] for r in rows})!=len(rows): raise ValueError('行业须唯一，最多100项')
    for r in rows:
        for k in ['portfolioWeight','benchmarkWeight']: number(r[k],k,0)
        for k in ['portfolioReturnPct','benchmarkReturnPct']: number(r[k],k,-100)
        url(r['sourceUrl'])
    if any(abs(sum(r[k] for r in rows)-1)>1e-8 for k in ['portfolioWeight','benchmarkWeight']): raise ValueError('两组权重必须各合计1，现金及未披露部分不能静默删掉或归一化')
    benchmark=sum(r['benchmarkWeight']*r['benchmarkReturnPct'] for r in rows)
    portfolio=sum(r['portfolioWeight']*r['portfolioReturnPct'] for r in rows)
    out=[]
    for r in rows:
        wp,wb,rp,rb=(r[k] for k in ['portfolioWeight','benchmarkWeight','portfolioReturnPct','benchmarkReturnPct'])
        allocation=(wp-wb)*(rb-benchmark);selection=wb*(rp-rb);interaction=(wp-wb)*(rp-rb)
        out.append({**r,'allocationPp':allocation,'selectionPp':selection,'interactionPp':interaction,'totalEffectPp':allocation+selection+interaction})
    totals={k:sum(r[k] for r in out) for k in ['allocationPp','selectionPp','interactionPp','totalEffectPp']}
    residual=portfolio-benchmark-totals['totalEffectPp']
    for value in [benchmark,portfolio,residual,*totals.values(),*(row[k] for row in out for k in ['allocationPp','selectionPp','interactionPp','totalEffectPp'])]:number(value,'归因派生结果')
    if abs(residual)>1e-8: raise ValueError('归因勾稽失败')
    actual=s.get('actualPortfolioReturnPct')
    if actual is not None: number(actual,'实际收益',-100)
    return {'type':'brinson-fachler-single-period','start':s['start'],'end':s['end'],'basis':s['basis'],'weightDate':s['weightDate'],'industrySystem':s['industrySystem'],'industryVersion':s['industryVersion'],'informationTiming':timing,'portfolioSnapshotReturnPct':portfolio,'benchmarkReturnPct':benchmark,'activeSnapshotReturnPp':portfolio-benchmark,'sectors':out,'totals':totals,'arithmeticResidualPp':residual,'actualPortfolioReturnPct':actual,'unexplainedActualVsSnapshotPp':None if actual is None else actual-portfolio,'formulaSource':'https://rpc.cfainstitute.org/sites/default/files/-/media/documents/book/rf-lit-review/2019/rflr-performance-attribution.pdf','riskNotice':NOTICE,'limitations':['固定披露权重估算，不能还原区间内交易；前十大只能分析已披露子组合','选股项含行业内部收益差，不等于剥离风险后的经理纯alpha','未披露资产不能假定零收益；子组合必须明确范围，不能冒称全基金','单期算术归因，不将跨期贡献简单相加为复利累计贡献','事后报告可作解释，不能伪称当时可获得的策略输入']}

def pool(s,store):
    name=s['name']
    if not isinstance(name,str) or not name.strip() or len(name)>100: raise ValueError('基金池名称无效')
    folder=store/'fund-pools'/key(name); versions=sorted(folder.glob('*.json'))
    previous=read(versions[-1]) if versions else {'name':name,'codes':[],'tags':[]}
    members=set(previous['codes'])
    for c in s.get('add',[]): members.add(code(c))
    for c in s.get('remove',[]): members.discard(code(c))
    tags=s.get('tags',previous.get('tags',[]))
    if not isinstance(tags,list) or any(not isinstance(t,str) or not t.strip() for t in tags): raise ValueError('标签须非空文字')
    result={'type':'fund-pool','name':name,'revision':previous.get('revision',0)+1,'codes':sorted(members),'tags':tags,'at':stamp(),'scoreModel':s.get('scoreModel',previous.get('scoreModel'))}
    if result['scoreModel'] is not None: validate_model(result['scoreModel'])
    dump(folder/(str(result['revision']).zfill(8)+'.json'),result)
    return result

def validate_model(model):
    if not isinstance(model,list) or not model or len({m['metric'] for m in model})!=len(model): raise ValueError('模型指标非空唯一')
    for m in model:
        if not isinstance(m['metric'],str) or not m['metric'] or m.get('direction') not in ['higher','lower']: raise ValueError('每个指标须明确方向')
        number(m['weight'],'评分权重',0)
    if abs(sum(m['weight'] for m in model)-1)>1e-8: raise ValueError('评分权重合计须1')

def score(s):
    pooldata=s['pool'];model=s.get('model',pooldata.get('scoreModel'));validate_model(model)
    members=pooldata['codes'];rows=s['rows'];bycode={r['code']:r for r in rows}
    if len(bycode)!=len(rows): raise ValueError('评分数据代码重复')
    # Do not compare differing metric windows/groups silently.
    if not s.get('comparisonScope') or not s.get('comparisonGroup'): raise ValueError('需共同指标窗口与可比组声明')
    good=[];excluded=[]
    for c in members:
        r=bycode.get(c);missing=[]
        for m in model:
            value=r.get('metrics',{}).get(m['metric']) if r else None
            if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value): missing.append(m['metric'])
        if missing: excluded.append({'code':c,'missingMetrics':missing});continue
        if r.get('comparisonScope')!=s['comparisonScope'] or r.get('comparisonGroup')!=s['comparisonGroup']: excluded.append({'code':c,'reason':'区间或组别不一致'});continue
        url(r['sourceUrl']);good.append(r)
    ranges={m['metric']:(min(r['metrics'][m['metric']] for r in good),max(r['metrics'][m['metric']] for r in good)) for m in model} if good else {}
    ranked=[]
    for r in good:
        components=[]
        for m in model:
            value=r['metrics'][m['metric']];lo,hi=ranges[m['metric']]
            if hi==lo:normalized=50
            elif math.isfinite(hi-lo):normalized=100*((value-lo)/(hi-lo))
            else:
                scale=max(abs(lo),abs(hi));normalized=100*((value/scale-lo/scale)/(hi/scale-lo/scale))
            number(normalized,'归一化分数')
            if hi!=lo and m['direction']=='lower': normalized=100-normalized
            components.append({**m,'value':value,'normalized':normalized,'weightedScore':normalized*m['weight']})
        ranked.append({'code':r['code'],'score':sum(x['weightedScore'] for x in components),'components':components,'sourceUrl':r['sourceUrl']})
    ranked.sort(key=lambda r:(-r['score'],r['code']))
    return {'type':'fund-pool-score','poolName':pooldata['name'],'comparisonScope':s['comparisonScope'],'comparisonGroup':s['comparisonGroup'],'ranked':ranked,'excluded':excluded,'model':model,'riskNotice':NOTICE,'limitations':['用户设定权重与池内min-max评分，不是投资推荐或未来收益评价','缺指标或口径不同整行不评分，不自动填充或重分配指标权重','池内无差异的指标统一50；少于2个完整样本评分不具横向区分意义','成员或样本变更会改变分数，跨版本不能直接比较']}

def reverse(s):
    asof=day(s['asOf']);period=day(s['reportDate']);target=s['target'];minimum=number(s.get('minimumWeight',0),'最低权重',0)
    if period>asof or target.get('kind') not in ['security','industry']: raise ValueError('目标或报告日期无效')
    if target['kind']=='security' and (not target.get('market') or not target.get('code')): raise ValueError('证券反查须市场和代码，不能只按简称')
    if target['kind']=='industry' and (not target.get('name') or not s.get('industrySystem') or not isinstance(s.get('industryVersion'),str) or not s['industryVersion'].strip()): raise ValueError('行业反查需分类体系')
    out=[];excluded=[];seen=set()
    for f in s['funds']:
        fid=code(f['id'])
        if fid in seen: raise ValueError('同报告期基金重复')
        seen.add(fid);url(f['sourceUrl'])
        if day(f['publishedAt'])>asof or day(f['reportDate'])!=period: excluded.append({'code':fid,'reason':'披露晚于截止日或报告期不同'});continue
        if s.get('poolCodes') is not None and fid not in s['poolCodes']: continue
        if f.get('weightBasis')!='fund-nav' or f.get('disclosureScope') not in ['top10','completeEquity','complete']: raise ValueError('需净资产权重与披露范围，不混用股票内部比例')
        if target['kind']=='industry' and (f.get('industrySystem')!=s['industrySystem'] or f.get('industryVersion')!=s['industryVersion']): excluded.append({'code':fid,'reason':'行业分类体系或版本不同或未知'});continue
        holdings=f['holdings'];weights=[];ids=set();unknown=0
        for h in holdings:
            identifier=(h.get('market'),h.get('code'),h.get('shareClass','ordinary'))
            if not identifier[0] or not identifier[1] or identifier in ids: raise ValueError('持仓缺市场代码或重复')
            ids.add(identifier);w=number(h['weight'],'持仓权重',0)
            if w>1: raise ValueError('权重须0至1，不是百分点')
            matches=(h['market']==target['market'] and h['code']==target['code'] and h.get('shareClass','ordinary')==target.get('shareClass','ordinary')) if target['kind']=='security' else h.get('industry')==target['name']
            if matches: weights.append(w)
            if not h.get('industry'): unknown+=1
        if sum(h['weight'] for h in holdings)>1+1e-6: raise ValueError('无杠杆净资产权重合计超过1')
        weight=sum(weights)
        if weights and weight>=minimum: out.append({'code':fid,'weight':weight,'reportDate':f['reportDate'],'publishedAt':f['publishedAt'],'disclosureScope':f['disclosureScope'],'sourceUrl':f['sourceUrl'],'matchCount':len(weights),'industryUnknownCount':unknown,'weightMeaning':'已披露权重；前十大为下限，非最新实时持仓'})
        elif f['disclosureScope']=='top10' or (target['kind']=='industry' and unknown): excluded.append({'code':fid,'reason':'披露不完整或行业未知，未命中不能证明无持仓'})
    out.sort(key=lambda r:(-r['weight'],r['code']))
    limit=s.get('limit',20)
    if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=500: raise ValueError('数量上限1至500')
    return {'type':'reverse-holdings','target':target,'reportDate':s['reportDate'],'matches':out[:limit],'matchedCount':len(out),'excluded':excluded,'sampleCount':len(seen),'riskNotice':NOTICE,'limitations':['仅查询输入报告/基金池，不是全市场搜索','报告日持仓不是当前持仓，前十大未命中不等于没有持有','行业结果依赖输入分类，未知不猜测；不推断踩雷必然损失']}

def archive(s,store):
    c=code(s['code']);folder=store/'fund-archives'/c
    record={'type':'fund-research-archive-entry','code':c,'id':str(uuid.uuid4()),'at':stamp(),'tags':s.get('tags',[]),'userNote':s.get('userNote',''),'riskLabels':s.get('riskLabels',[]),'documentSummaries':s.get('documentSummaries',[]),'results':[]}
    if not isinstance(record['tags'],list) or any(not isinstance(x,str) for x in record['tags']) or not isinstance(record['userNote'],str): raise ValueError('标签或笔记无效')
    files=s.get('resultFiles',[])
    if not isinstance(files,list) or any(not isinstance(file,str) or not file.strip() for file in files):raise ValueError('结果文件须为非空路径列表')
    prepared=[]
    for file in files:
        p=Path(file);raw=p.read_bytes()
        if len(raw)>20000000: raise ValueError('单份结果上限20MB')
        result=json.loads(raw.decode('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)
        if not isinstance(result,dict):raise ValueError('归档结果须为对象')
        if result.get('code') and result['code']!=c: raise ValueError('归档结果主体不一致')
        if 'subjectCodes' in result:
            subjects=result['subjectCodes']
            if not isinstance(subjects,list) or not subjects or any(not isinstance(x,str) or not re.fullmatch(r'\d{6}',x) for x in subjects) or len(subjects)!=len(set(subjects)) or c not in subjects:raise ValueError('归档结果主体不一致或主体列表无效')
        digest=hashlib.sha256(raw).hexdigest();dest=folder/'results'/(digest+'.json')
        if dest.exists() and dest.read_bytes()!=raw: raise ValueError('归档冲突')
        prepared.append((dest,raw))
        record['results'].append({'sha256':digest,'archive':str(dest.relative_to(folder)),'resultType':result.get('type')})
    # Validate the complete selection before persisting any result.
    for dest,raw in prepared:
        dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():
            with dest.open('xb') as f:f.write(raw)
    dump(folder/'entries'/(record['at'].replace(':','-')+'-'+record['id']+'.json'),record)
    return record

def documents(s):
    from pypdf import PdfReader
    p=Path(s['pdf']);raw=p.read_bytes();digest=hashlib.sha256(raw).hexdigest();url(s['sourceUrl'])
    if digest!=s['sha256'] or day(s['publishedAt'])>day(s['asOf']): raise ValueError('PDF哈希不符或晚于截止日')
    doc=PdfReader(p)
    if len(doc.pages)>300: raise ValueError('单次最多300页，需拆分文档范围')
    front=''.join((page.extract_text() or '') for page in doc.pages[:5]);compact=lambda t:re.sub(r'\s+','',t)
    if not s.get('identityText') or compact(s['identityText']) not in compact(front): raise ValueError('首页主体不匹配')
    terms=s.get('keywords',['投资范围','投资限制','禁止','业绩报酬','封闭期','侧袋','流动性','港股','基金经理报告'])
    if not isinstance(terms,list) or not terms or len(terms)>20 or any(not isinstance(t,str) or not t for t in terms): raise ValueError('关键词无效')
    candidates=[];empty=[]
    for no,page in enumerate(doc.pages,1):
        text=page.extract_text() or ''
        if not text.strip(): empty.append(no);continue
        for term in terms:
            pos=0
            while True:
                hit=text.find(term,pos)
                if hit<0: break
                candidates.append({'keyword':term,'page':no,'excerpt':text[max(0,hit-100):hit+500],'sourceUrl':s['sourceUrl'],'documentSha256':digest,'status':'text-candidate-not-semantic-verification'})
                if len(candidates)>1000: raise ValueError('命中过多，缩小关键词')
                pos=hit+len(term)
    return {'type':'document-clause-search','publishedAt':s['publishedAt'],'sourceUrl':s['sourceUrl'],'documentSha256':digest,'candidates':candidates,'emptyTextPages':empty,'limitations':['关键词定位可能命中目录或重复内容；需阅读上下文才回答合同是否允许','扫描页未识别，不将未命中当不存在条款','只解析所提供公开PDF，不后台抓取；摘要必须引用实际页码摘录']}

COMMANDS={'brinson':brinson,'score':score,'reverse':reverse,'documents':documents}
def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=list(COMMANDS)+['pool','archive']);p.add_argument('input',type=Path);p.add_argument('--store',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists(): raise ValueError('输出已存在')
    s=read(a.input)
    if a.command in ['pool','archive']:
        if not a.store: raise ValueError('需用户资料目录--store')
        result=(pool if a.command=='pool' else archive)(s,a.store)
    else: result=COMMANDS[a.command](s)
    dump(a.out,result)
if __name__=='__main__': main()
