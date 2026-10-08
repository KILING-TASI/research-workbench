"""Conservative gap audit, append-only local knowledge cards and numeric source reconciliation."""
import datetime as dt
import hashlib
import json
import os
import re
import shutil
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse
from research_workflow import digest,file_digest,load

def _date(value,name):
    if not isinstance(value,str):raise ValueError(name+'须为日期')
    if dt.date.fromisoformat(value).isoformat()!=value:raise ValueError(name+'须为YYYY-MM-DD')
    return value

def gap_analysis(spec):
    result=load(spec['resultPath'])
    if result.get('type')!='research-template-result':raise ValueError('输入须为研究模板结果')
    depth=spec.get('depth','basic')
    if depth not in ('basic','full'):raise ValueError('depth须为basic或full')
    issues=[]
    for gap in result.get('gaps',[]):
        issues.append({'category':'data-or-calculation','entity':gap.get('code'),'missing':gap.get('reason'),
            'impact':'阻断计算' if result.get('result') is None else '影响证据解释或来源可靠性',
            'priority':'high' if result.get('result') is None else 'medium','nextStep':'查看原采集状态或报告原文'})
    if result.get('template')=='fund-comparison':
        obj=result.get('result') or {}
        if obj.get('start') and obj.get('end'):
            issues.append({'category':'time-coverage','availablePeriod':{'start':obj['start'],'end':obj['end']},
                'missing':'未指定要求覆盖的完整历史或关键报告期',
                'impact':'只能解释共同观测区间','priority':'low','nextStep':'按研究问题明确期初和报告期'})
        for source in result['lineage']['sources']:
            code=source['code']
            if not source.get('sourceUrl'):
                issues.append({'category':'provenance','entity':code,'missing':'历史来源地址','impact':'无法回查原数据源','priority':'high','nextStep':'重新采集并登记来源'})
            if source.get('sourceVerification')!='official-original-verified':
                issues.append({'category':'source-verification','entity':code,'missing':'历史净值和分红逐项官方原文核验',
                    'impact':'数值可计算但源数据仍为待核验','priority':'medium','nextStep':'取得官方净值或报告并比对'})
            if not source.get('historyCount'):
                issues.append({'category':'data','entity':code,'missing':'净值历史','impact':'无法横向对比','priority':'high','nextStep':'核查代码与接口'})
            if depth=='full':
                for item in ['完整持仓报告','历史费率及份额类别']:
                    issues.append({'category':'extension','entity':code,'missing':item,
                        'impact':'不影响本次净值指标；阻碍完整基金尽调','priority':'low',
                        'nextStep':'提供对应日期的基金官方报告或合同'})
    elif result.get('template')=='portfolio-diagnostic':
        if not (result.get('result') or {}).get('stressComplete'):
            issues.append({'category':'scenario','missing':'至少一种持仓类别的冲击假设',
                'impact':'组合总损益留空','priority':'high','nextStep':'明确该资产类别冲击或移除未覆盖情景'})
        issues.append({'category':'source-verification','missing':'持仓金额及资产分类的账户或报告核验',
            'impact':'计算基于用户输入','priority':'medium','nextStep':'提供带日期的持仓记录'})
        if depth=='full':
            issues.append({'category':'extension','missing':'底层穿透、交易成本与流动性数据',
                'impact':'一次冲击不能推导路径回撤或变现成本','priority':'low','nextStep':'逐层补充底层持仓及交易条件'})
    periods=spec.get('requiredPeriods',[]);available=spec.get('availableReports',[])
    if not isinstance(periods,list) or not isinstance(available,list):raise ValueError('报告期清单须为列表')
    available_keys={(r.get('code'),r.get('component'),r.get('period')) for r in available if isinstance(r,dict)}
    for request in periods:
        if not isinstance(request,dict) or not all(request.get(k) for k in ['code','component','period']):raise ValueError('必需报告期缺少对象、类型或期间')
        _date(request['period'],'requiredPeriods.period')
        key=(request['code'],request['component'],request['period'])
        if key not in available_keys:
            issues.append({'category':'time-coverage','entity':request['code'],'period':request['period'],
                'missing':request['component']+'原文报告未登记',
                'impact':'该报告期的持仓或财务解读无法核验','priority':'high',
                'nextStep':'获取该期原文并加入版本知识卡'})
    ordered=sorted(issues,key=lambda x:({'high':0,'medium':1,'low':2}[x['priority']],x.get('entity') or '',x['category']))
    return {'type':'research-gap-analysis','template':result['template'],'resultStatus':result['status'],
        'depth':depth,'issues':ordered,'counts':{p:sum(i['priority']==p for i in ordered) for p in ['high','medium','low']},
        'interpretation':'优先级依据缺口是否阻断本次计算或原始数据复核；不构成统计置信度评分',
        'limitation':'只检查已登记输入和模板要求，无法自动发现未披露事实或证明全部资料齐全'}

def _safe_code(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{6}',value):raise ValueError('知识卡代码须为六位数字')
    return value

def _version_paths(store,code,kind=None):
    root=Path(store)/'research-data'/'knowledge'
    if kind is None:
        choices=[p for p in root.glob('*/'+code+'/versions') if p.is_dir()]
        if len(choices)>1:raise ValueError('代码对应多个证券品种，请明确kind')
        folder=choices[0] if choices else root/'unknown'/code/'versions'
    else:
        if kind not in ('fund','stock','etf','bond','convertible','other'):raise ValueError('kind无效')
        folder=root/kind/code/'versions'
    return folder,sorted(folder.glob('*.json')) if folder.exists() else []

def _verify_chain(paths):
    previous=None;records=[]
    for position,path in enumerate(paths,1):
        row=load(path)
        if row.get('version')!=position or row.get('previousVersionHash')!=previous:
            raise ValueError('知识卡版本链不连续或遭修改')
        signature=row.get('versionHash');body={k:v for k,v in row.items() if k!='versionHash'}
        if digest(body)!=signature:raise ValueError('知识卡版本哈希不一致')
        records.append(row);previous=signature
    return records

def _archive(path,folder,extension):
    source=Path(path)
    if not source.is_file() or source.stat().st_size>100*1024*1024:raise ValueError('来源文件不存在或超过100MiB')
    signature=file_digest(source);folder.mkdir(parents=True,exist_ok=True)
    target=folder/(signature+extension)
    if not target.exists():
        tmp=folder/(signature+'.pending')
        shutil.copyfile(source,tmp)
        if file_digest(tmp)!=signature:raise ValueError('来源副本哈希不一致')
        os.replace(tmp,target)
    elif file_digest(target)!=signature:raise ValueError('既有归档文件哈希不一致')
    return {'path':str(target.resolve()),'sha256':signature,'bytes':source.stat().st_size,'originalPath':str(source.resolve())}

def knowledge_add(spec,workspace):
    code=_safe_code(spec.get('code'));_date(spec.get('period'),'period');_date(spec.get('publishedAt'),'publishedAt')
    if spec['publishedAt']<spec['period']:raise ValueError('发布日早于报告期')
    if spec.get('kind') not in ('fund','stock','etf','bond','convertible','other'):raise ValueError('kind无效')
    facts=spec.get('facts')
    if not isinstance(facts,list) or not facts:raise ValueError('facts不得为空')
    ids=[]
    for fact in facts:
        if not isinstance(fact,dict) or any(not fact.get(k) for k in ['id','field','unit','currency','basis','statementScope']):raise ValueError('事实字段缺少ID、口径或单位')
        if fact.get('value') is None:raise ValueError('事实数值为空')
        try:
            if not Decimal(str(fact['value'])).is_finite():raise ValueError('非有限数值')
        except InvalidOperation:raise ValueError('事实数值格式无效')
        ids.append(fact['id'])
    if len(set(ids))!=len(ids):raise ValueError('事实ID重复')
    if not spec.get('sourcePath'):raise ValueError('需提供本地原文PDF；不根据链接猜文件')
    pdf=Path(spec['sourcePath'])
    with pdf.open('rb') as stream:
        if stream.read(5)!=b'%PDF-':raise ValueError('来源文件不是PDF')
    folder,existing=_version_paths(workspace,code,spec['kind']);folder.mkdir(parents=True,exist_ok=True)
    lock=folder.parent/'write.lock'
    try:
        descriptor=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError:raise ValueError('知识卡正被写入；请稍后重试，不要并发覆盖')
    try:
        os.close(descriptor)
        records=_verify_chain(existing)
        blobs=folder.parent/'blobs'
        original=_archive(pdf,blobs,'.pdf')
        verification=None;verified_fields={};candidate=None
        if spec.get('verificationPath'):
            candidate=load(spec['verificationPath'])
            if not isinstance(candidate,dict):raise ValueError('核验记录须为对象')
            verification=_archive(spec['verificationPath'],blobs,'.json')
            if (candidate.get('type')=='original-document-verification' and candidate.get('status')=='passed'
                    and candidate.get('sha256')==original['sha256']
                    and spec.get('sourceUrl') and candidate.get('sourceUrl')==spec['sourceUrl']
                    and candidate.get('reportDate')==spec['period']
                    and candidate.get('publishedAt')==spec['publishedAt']):
                fields=candidate.get('fields',[])
                if not isinstance(fields,list) or any(not isinstance(f,dict) or not isinstance(f.get('id'),str) or not f['id'].strip() for f in fields):raise ValueError('核验字段须为带明确ID的对象列表')
                if len({f['id'] for f in fields})!=len(fields):raise ValueError('核验字段ID重复，不能静默选择')
                verified_fields={f.get('id'):f for f in candidate.get('fields',[])
                    if f.get('verification') in ('exact-table-cell','native-scoped-table-cell','native-exact-excerpt') or f.get('status')=='matched'}
        verified=True
        for fact in facts:
            found=verified_fields.get(fact['id'])
            if not found or not fact.get('originalLabel') or fact['originalLabel']!=found.get('label'):
                verified=False;break
            try:
                reference=found.get('actual',found.get('value'))
                if Decimal(str(fact['value']))!=Decimal(str(reference)):verified=False;break
            except InvalidOperation:verified=False;break
        item={'type':'research-knowledge-version','schemaVersion':1,'code':code,'kind':spec['kind'],
            'version':len(records)+1,'previousVersionHash':records[-1]['versionHash'] if records else None,
            'recordedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'period':spec['period'],
            'publishedAt':spec['publishedAt'],'sourceUrl':spec.get('sourceUrl'),
            'original':original,'verification':verification,'evidenceLevel':'original-fields-matched-authority-unverified' if verified else 'supplied-pdf-unverified-fields',
            'sourceAuthorityVerification':'not-verified-by-this-entry',
            'facts':facts,'note':spec.get('note','')}
        item['versionHash']=digest(item)
        if (records and digest({k:item[k] for k in ['period','publishedAt','sourceUrl','facts','note']})==digest({k:records[-1].get(k) for k in ['period','publishedAt','sourceUrl','facts','note']})
                and original['sha256']==records[-1]['original']['sha256'] and item['evidenceLevel']==records[-1]['evidenceLevel']):
            raise ValueError('与上一版本内容相同，不重复追加')
        path=folder/(f'{item["version"]:06d}-{item["versionHash"][:12]}.json')
        with path.open('x',encoding='utf-8') as stream:json.dump(item,stream,ensure_ascii=False,indent=2,allow_nan=False)
        old={f['id']:f for f in records[-1]['facts']} if records else {}
        new_period=bool(records and records[-1]['period']!=item['period'])
        changes=[{'id':f['id'],'change':'new-period' if new_period else 'added' if f['id'] not in old else 'revised' if f!=old[f['id']] else 'unchanged'} for f in facts]
        changes.extend({'id':x,'change':'removed'} for x in old if x not in ids)
        return {'type':'research-knowledge-write','code':code,'version':item['version'],
            'versionPath':str(path.resolve()),'versionHash':item['versionHash'],
            'evidenceLevel':item['evidenceLevel'],'changes':changes}
    finally:
        lock.unlink(missing_ok=True)

def knowledge_show(spec,workspace):
    code=_safe_code(spec.get('code'));_,paths=_version_paths(workspace,code,spec.get('kind'))
    records=_verify_chain(paths)
    return {'type':'research-knowledge-card','code':code,'kind':records[0]['kind'] if records else spec.get('kind'),
        'versionCount':len(records),
        'versions':[{'version':r['version'],'period':r['period'],'publishedAt':r['publishedAt'],
                     'recordedAt':r['recordedAt'],'evidenceLevel':r['evidenceLevel'],
                     'originalSha256':r['original']['sha256'],'versionHash':r['versionHash'],
                     'facts':r['facts']} for r in records],
        'limitations':['不同报告期数值不得直接判作冲突','旧版与原PDF副本保留；外部源的历史首次上线时间未自动核验']}

def cross_validate(spec,workspace=None):
    as_of=_date(spec.get('asOf'),'asOf')
    observations=spec.get('observations',[])
    if not isinstance(observations,list):raise ValueError('observations须为列表')
    observations=list(observations)
    for selection in spec.get('knowledgeCodes',[]):
        code=selection.get('code') if isinstance(selection,dict) else selection
        kind=selection.get('kind') if isinstance(selection,dict) else None
        _safe_code(code)
        if workspace is None:raise ValueError('knowledgeCodes需要知识卡工作目录')
        _,paths=_version_paths(workspace,code,kind)
        for path,version in zip(paths,_verify_chain(paths)):
            for fact in version['facts']:
                observations.append({'entityId':version['kind']+':'+code,'field':fact['field'],
                    'period':version['period'],'periodBasis':fact.get('periodBasis',fact['basis']),
                    'statementScope':fact['statementScope'],'basis':fact.get('measurementBasis','reported'),
                    'unit':fact['unit'],'currency':fact['currency'],'publishedAt':version['publishedAt'],
                    'sourceId':code+'-v'+str(version['version']),'sourceUrl':version.get('sourceUrl'),
                    'sourceHash':version['original']['sha256'],'sourceTier':version['evidenceLevel'],
                    'versionPath':str(path.resolve()),'retrievedAt':version['recordedAt'],'value':fact['value']})
    if not observations or len(observations)>10000:raise ValueError('观测总数须为1至10000项')
    absolute=Decimal(str(spec.get('absoluteTolerance','0')))
    relative=Decimal(str(spec.get('relativeTolerancePct','0')))
    if absolute<0 or relative<0 or not absolute.is_finite() or not relative.is_finite():raise ValueError('容差无效')
    groups={};excluded=[];uncomparable={}
    keys=['entityId','field','period','periodBasis','statementScope','basis','unit','currency']
    for index,row in enumerate(observations):
        if not isinstance(row,dict) or any(not isinstance(row.get(k),str) or not row[k] for k in keys+['sourceId','publishedAt']):raise ValueError('观测缺少对象、口径、来源或日期')
        _date(row['period'],'period');_date(row['publishedAt'],'publishedAt')
        if row['period']>row['publishedAt']:raise ValueError('报告期不能晚于披露日')
        if row['publishedAt']>as_of:excluded.append({'index':index,'reason':'发布晚于截止日'});continue
        try:value=Decimal(str(row['value']))
        except (InvalidOperation,KeyError):raise ValueError('观测数值无效')
        if not value.is_finite():raise ValueError('非有限数值')
        retrieved=row.get('retrievedAt')
        if retrieved is not None:
            if not isinstance(retrieved,str) or not retrieved.strip():raise ValueError('取得时间须为ISO日期或时间戳')
            _date(retrieved[:10],'retrievedAt')
            if retrieved[:10]<row['publishedAt']:raise ValueError('取得日不能早于披露日')
            if len(retrieved)>10:
                try:dt.datetime.fromisoformat(retrieved)
                except ValueError as exc:raise ValueError('取得时间戳格式无效') from exc
        key=tuple(row[k] for k in keys)
        item={'sourceId':row['sourceId'],'value':str(value),'publishedAt':row['publishedAt'],
              'retrievedAt':row.get('retrievedAt'),'sourceUrl':row.get('sourceUrl'),
              'sourceHash':row.get('sourceHash'),'publisher':row.get('publisher') or urlparse(row.get('sourceUrl') or '').hostname,
              'claimedSourceTier':row.get('sourceTier','unclassified'),'versionPath':row.get('versionPath'),
              'pointInTime':'retrospective-copy' if row.get('retrievedAt') and str(row['retrievedAt'])[:10]>as_of else 'retrieval-date-not-proven' if not row.get('retrievedAt') else 'retrieved-by-cutoff'}
        groups.setdefault(key,[]).append(item)
        uncomparable.setdefault((row['entityId'],row['field']),set()).add(key)
    results=[]
    for key,items in groups.items():
        # Connected components merge copies AND publisher-related observations.
        # Two different PDFs from one publisher are not two independent sources.
        clusters=[]
        for i,r in enumerate(items):
            tags={('hash',r['sourceHash'])} if r['sourceHash'] else set()
            if r['publisher']:tags.add(('publisher',r['publisher'].strip().lower()))
            tags.add(('sourceId',r['sourceId']))
            touching=[c for c in clusters if c['tags'] & tags]
            members=[i]
            for c in touching:tags.update(c['tags']);members+=c['members'];clusters.remove(c)
            clusters.append({'tags':tags,'members':members})
        values=[Decimal(x['value']) for x in items]
        spread=max(values)-min(values)
        scale=max((abs(v) for v in values),default=Decimal(0))
        tolerance=max(absolute,scale*relative/100)
        status='insufficient-independent-sources' if len(clusters)<2 else 'consistent-within-tolerance' if spread<=tolerance else 'divergence'
        results.append({'identity':dict(zip(keys,key)),'status':status,'sources':items,
            'distinctSourceCount':len(clusters),'sourceClusters':[[items[i]['sourceId'] for i in c['members']] for c in clusters],
            'numericAgreement':'consistent-within-tolerance' if spread<=tolerance else 'divergence',
            'maxAbsoluteDifference':str(spread),'toleranceApplied':str(tolerance)})
    incompatible=[{'entityId':key[0],'field':key[1],'differentBases':[dict(zip(keys,parts)) for parts in sorted(versions)]}
                  for key,versions in uncomparable.items() if len(versions)>1]
    return {'type':'research-cross-validation','asOf':as_of,'groups':results,'excluded':excluded,
        'incomparable':incompatible,'summary':{s:sum(r['status']==s for r in results) for s in
            ['consistent-within-tolerance','divergence','insufficient-independent-sources']},
        'limitations':['仅同对象、字段、报告期、期间类型、报表范围、计价口径、单位和币种比较；不自动换算',
            '来源等级为输入声明，未在本入口证明官方身份；差异原因须核对原文，不能自动归因']}
