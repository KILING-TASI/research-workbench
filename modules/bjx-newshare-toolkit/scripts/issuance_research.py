"""Evidence-gated BJX research workflow. No trading, model training or future price forecast."""
import argparse, copy, datetime as dt, json, re
from decimal import Decimal
from pathlib import Path
from allocation_cash import calculate, collision, LABELS, number
from research_evidence import export, validate, conflicts, package, sha, canonical, load, timestamp, now

NUMERIC_VERIFIED={'original-text-matched','exact-table-cell-with-header'}
DEFAULT_FIELDS=['price','maxShares','onlineFinalShares','refundDate','ratePct','strategicShares','greenshoeShares',
    'initialIssueShares','initialOnlineShares','postIssueSharesBefore','postIssueSharesFull','validSubscriptionShares']

def indexed(evidence):return {n['id']:n for n in validate(evidence['nodes'])}
def refs(ids,nodes):
    if not ids or any(i not in nodes for i in ids):raise ValueError('证据引用缺失或不存在')
    return [nodes[i] for i in ids]
def original_refs(ids,nodes):
    rows=refs(ids,nodes)
    if any(n['kind']!='original' or n['verification'] not in NUMERIC_VERIFIED for n in rows):raise ValueError('需要逐字段原文数值匹配证据')
    return rows
def same_value(value,unit,metric,ids,nodes):
    rows=original_refs(ids,nodes)
    if not any(n['metric']==metric and n.get('unit')==unit and number(n['value'],metric,Decimal('-1e30'))==number(value,metric,Decimal('-1e30')) for n in rows):raise ValueError('数值、指标或单位未与原文证据一致:'+metric)
    return rows

def panel(spec,evidence):
    nodes=indexed(evidence);groups=conflicts(evidence)['groups'];blocked={(r['subject'],r['metric']) for r in groups if r['status']=='unresolved'}
    requested=spec.get('fields',DEFAULT_FIELDS)
    if not isinstance(requested,list) or len(requested)!=len(set(requested)):raise ValueError('查询字段须唯一列表')
    used=set(spec.get('usedEvidenceIds',[]))
    if used-set(nodes):raise ValueError('计算使用记录引用未知证据')
    rows=[]
    for metric in requested:
        candidates=[n for n in nodes.values() if n['subject']==spec['code'] and n['metric']==metric]
        replaced={n.get('supersedes') for n in candidates if n.get('supersedes')}
        active=[n for n in candidates if n.get('version') not in replaced]
        conflict=(spec['code'],metric) in blocked
        n=active[-1] if active and not conflict else None
        status='version-conflict' if conflict else 'missing-unknown' if not n or n['kind']=='missing' else 'original-numeric-matched' if n['kind']=='original' and n.get('value') is not None and n['verification'] in NUMERIC_VERIFIED else 'third-party' if n['kind']=='third-party' else 'assumption' if n['kind']=='assumption' else 'pending-review'
        rows.append({'metric':metric,'value':n.get('value') if n else None,'unit':n.get('unit') if n else None,'status':status,
            'candidates':active,'usedInCalculation':any(x['id'] in used for x in active),'publicationTimeCertified':False})
    total=len(rows);covered=sum(r['value'] is not None for r in rows);matched=sum(r['status']=='original-numeric-matched' for r in rows)
    return {'fields':rows,'quality':{'requestedCount':total,'availableCount':covered,'originalNumericMatchedCount':matched,
        'coveragePct':str(Decimal(covered)/total*100) if total else None,'originalMatchedPct':str(Decimal(matched)/total*100) if total else None,
        'conflictCount':sum(r['status']=='version-conflict' for r in rows),'missingCount':sum(r['status']=='missing-unknown' for r in rows),
        'latestDeclaredPublication':max((n['publishedAt'] for n in nodes.values() if n.get('publishedAt')),default=None),
        'freshness':'latest-effective-version-not-independently-confirmed','investmentQualityScore':None},
        'limitations':['原文数值匹配不等于线上来源、字段语义和首次公开时间均获认证','计算使用状态来自实际工作流记录或显式引用，不凭有值推断','覆盖率分母是所查询字段，不是全套公告字段']}

def rate(spec,nodes,purpose='scenario',asof=None):
    grade=spec.get('grade','D');basis=spec.get('basis');ids=spec.get('evidenceIds',[])
    if grade not in ['A','B','C','D']:raise ValueError('配售率等级无效')
    if grade=='D':return {'grade':'D','ratePct':None,'usable':False,'reason':'未知或未核验，不计算获配'}
    if not basis:raise ValueError('配售率依据缺失')
    if purpose=='predecision' and grade in ['A','B']:raise ValueError('实际结果不得进入事前目标预测；事前仅明确情景C')
    if grade=='C':
        value=number(spec['value'],'ratePct',maximum=Decimal(100));proof=refs(ids,nodes) if ids else []
        if any(n['kind'] not in ['assumption','third-party'] for n in proof):raise ValueError('C级需明确假设或待核验来源，不能借用实际结果冒充事前假设')
    elif grade=='A':
        value=number(spec['value'],'ratePct',maximum=Decimal(100));proof=same_value(value,'%','ratePct',ids,nodes)
    else:
        online=number(spec['onlineShares'],'onlineShares',Decimal(1));total=number(spec['validSubscriptionShares'],'validSubscriptionShares',Decimal(1))
        if online>total or online!=online.to_integral_value() or total!=total.to_integral_value():raise ValueError('股数不完整或非超额申购，不能套比例公式')
        a=same_value(online,'股',spec.get('onlineMetric','onlineFinalShares'),spec['onlineEvidenceIds'],nodes)
        b=same_value(total,'股',spec.get('totalMetric','validSubscriptionShares'),spec['totalEvidenceIds'],nodes)
        online_basis=spec.get('onlineBasis',spec.get('quantityBasis'));total_basis=spec.get('totalBasis',spec.get('quantityBasis'))
        if not online_basis or not total_basis or any(n.get('basis')!=online_basis for n in a) or any(n.get('basis')!=total_basis for n in b):raise ValueError('正式网上发行量与有效申购量需逐项明确结果口径')
        value=online/total*100;proof=a+b;ids=list(dict.fromkeys(spec['onlineEvidenceIds']+spec['totalEvidenceIds']))
    if asof and any(n.get('publishedAt') and dt.date.fromisoformat(n['publishedAt'][:10])>dt.date.fromisoformat(asof) for n in proof):raise ValueError('配售率证据晚于截止日')
    return {'grade':grade,'ratePct':str(value),'usable':True,'basis':basis,'evidenceIds':ids,
        'verification':'user-declared-scenario' if grade=='C' else 'original-numeric-matched-semantic-and-publication-review-required',
        'notProbability':True}

def graded_allocation(spec,nodes,purpose='scenario',asof=None):
    declarations=spec.get('rateEvidence',{})
    if set(declarations)!=set(LABELS):raise ValueError('需三档配售率证据等级')
    assessed={k:rate(declarations[k],nodes,purpose,asof) for k in LABELS}
    for proof in assessed.values():
        if any(nodes[i]['subject']!=spec['allocation']['code'] for i in proof.get('evidenceIds',[])):raise ValueError('配售率证据与申购股票主体不一致')
    if any(not x['usable'] for x in assessed.values()):return {'status':'blocked-missing-rate','rateEvidence':assessed,'scenarios':None}
    allocation=copy.deepcopy(spec['allocation']);values={k:x['ratePct'] for k,x in assessed.items()}
    if allocation.get('ratesPct') and any(number(allocation['ratesPct'][k],k)!=number(values[k],k) for k in LABELS):raise ValueError('原配售率与证据分级值不同')
    allocation['ratesPct']=values;allocation['rateBasis']='; '.join(k+':'+assessed[k]['basis'] for k in LABELS)
    result=calculate(allocation)
    return {'status':'calculated-conditional','rateEvidence':assessed,'result':result,'allocationSpec':allocation}

def structure(spec,nodes):
    values={};proof={};gaps=[]
    for field in ['price','preIssueShares','postIssueSharesBefore','initialIssueShares','initialOnlineShares','strategicShares','overallocatedShares','actualNewShares','actualRepurchasedShares','adjustedProfit']:
        item=spec.get(field)
        if item is None:values[field]=None;gaps.append(field);continue
        v=number(item['value'],field,Decimal('-1e30') if field=='adjustedProfit' else Decimal(0));values[field]=v
        if field not in ['price','adjustedProfit'] and v!=v.to_integral_value():raise ValueError('股数须整数')
        ids=item.get('evidenceIds',[])
        if item.get('kind')=='original':
            matched=same_value(v,item['unit'],item.get('metric',field),ids,nodes)
            if field=='adjustedProfit':
                periods={n.get('period') for n in matched if n['metric']==item.get('metric',field)}
                if len(periods)!=1 or None in periods:raise ValueError('扣非利润缺少唯一年度')
                period=next(iter(periods))
                if spec.get('profitPeriod') and spec['profitPeriod']!=period:raise ValueError('扣非利润年度与估值年度不一致')
                spec={**spec,'profitPeriod':period}
        elif item.get('kind')!='assumption' or not item.get('basis'):raise ValueError('发行结构输入需原文证据或明确假设')
        expected='元/股' if field=='price' else 'CNY' if field=='adjustedProfit' else '股'
        if item['unit']!=expected:raise ValueError('发行结构字段单位不符')
        proof[field]={'kind':item['kind'],'evidenceIds':ids,'basis':item.get('basis')}
    pre=values['preIssueShares'];initial=values['initialIssueShares'];over=values['overallocatedShares'];new=values['actualNewShares'];buy=values['actualRepurchasedShares'];online=values['initialOnlineShares']
    before=values['postIssueSharesBefore']
    if before is not None and initial is not None:
        inferred=before-initial
        if inferred<=0 or (pre is not None and inferred!=pre):raise ValueError('发行前后股本勾稽不符')
        if pre is None:
            pre=inferred;gaps.remove('preIssueShares');proof['preIssueShares']={'kind':'derived','formula':'postIssueSharesBefore-initialIssueShares','dependsOn':['postIssueSharesBefore','initialIssueShares']}
    if initial is not None and online is not None and online>initial:raise ValueError('初始网上量超过初始发行量')
    if initial is not None and online is not None and values['strategicShares'] is not None and online+values['strategicShares']>initial:raise ValueError('初始发行结构合计超过发行量，需核对延期交付口径')
    if over is not None and any(x is not None and x>over for x in [new,buy]):raise ValueError('实际增发/购回超过超额配售量')
    if over is not None and new is not None and buy is not None and new+buy!=over:raise ValueError('增发与购回未能解释超额配售总量')
    rows=[]
    for label,extra in [('before-greenshoe',Decimal(0)),('full-exercise-hypothetical',over),('actual-implementation',new)]:
        issue=initial+extra if initial is not None and extra is not None else None
        shares=pre+issue if pre is not None and issue is not None else None
        cap=shares*values['price'] if shares is not None and values['price'] is not None else None
        profit=values['adjustedProfit'];pe=cap/profit if cap is not None and profit is not None and profit>0 else None
        rows.append({'basis':label,'issueShares':str(issue) if issue is not None else None,'postIssueShares':str(shares) if shares is not None else None,
            'marketCap':str(cap) if cap is not None else None,'adjustedPe':str(pe) if pe is not None else None,
            'notActual':label=='full-exercise-hypothetical','formula':'post=pre+initial+additional; marketCap=post*price; PE=marketCap/positiveAdjustedProfit'})
    return {'views':rows,'inputEvidence':proof,'profitPeriod':spec.get('profitPeriod'),'missing':gaps,
        'onlineSharesAfterOverallotment':str(online+over) if online is not None and over is not None and spec.get('overallotmentDestination')=='online' else None,
        'limitations':['不把超额配售量当作实际新增股份，购回与增发分别列示','全额行使仅是假设口径；未内置战配/绿鞋法定比例，须核验适用规则','延期交付战略股份不能与非延期战配份额混用']}

def timeline(spec,nodes):
    events=[];asof=dt.date.fromisoformat(spec['asOf'])
    for e in spec.get('events',[]):
        if not e.get('id') or not e.get('subject') or not e.get('type'):raise ValueError('事件身份缺失')
        rows=refs(e.get('evidenceIds',[]),nodes)
        if any(n.get('publishedAt') and dt.date.fromisoformat(n['publishedAt'][:10])>asof for n in rows):raise ValueError('事件依据晚于研究截止日')
        day=e.get('date');conditions=e.get('conditions',[])
        if day:dt.date.fromisoformat(day)
        events.append({**e,'date':day,'status':'conditional-date' if conditions else 'declared-date-with-evidence' if day else 'date-unknown',
            'verification':'event-semantic-mapping-user-reviewed','priceImpact':None})
    if len({e['id'] for e in events})!=len(events):raise ValueError('事件ID重复')
    events.sort(key=lambda e:(e['date'] is None,e['date'] or '',e['id']))
    return {'events':events,'missingDates':[e['id'] for e in events if not e['date']],
        'limitations':['仅列有证据引用的事件，语义映射由使用者复核','限售期、延期交付、稳定期和实施结果分别登记；未知日期不按默认月份填充','解禁不等于实际卖出，不推断价格影响']}

def rules(spec,nodes):
    versions=spec.get('versions',[]);known={};pending=[]
    for r in versions:
        if not r.get('id') or r['id'] in known:raise ValueError('规则ID缺失或重复')
        proof=refs(r.get('evidenceIds',[]),nodes)
        effective=r.get('effectiveDate');published=r.get('publishedAt')
        if effective:dt.date.fromisoformat(effective)
        if published:dt.date.fromisoformat(published)
        status='reviewed-applicability' if r.get('reviewed') is True and effective and published and all(n['kind']=='original' for n in proof) else 'pending-applicability'
        known[r['id']]={**r,'status':status}
        if status!='reviewed-applicability':pending.append(r['id'])
    before=known.get(spec.get('before'));after=known.get(spec.get('after'));changes=[]
    if before and after:
        for key in sorted(set(before.get('parameters',{}))|set(after.get('parameters',{}))):
            a=before.get('parameters',{}).get(key);b=after.get('parameters',{}).get(key)
            if a!=b:changes.append({'parameter':key,'before':a,'after':b,'affectedFields':spec.get('impactMap',{}).get(key,[]),'automaticCalculationUpdate':False})
    requested=spec.get('selected');selected=known.get(requested);asof=dt.date.fromisoformat(spec['asOf'])
    eligible=bool(selected and selected['status']=='reviewed-applicability' and dt.date.fromisoformat(selected['effectiveDate'])<=asof and dt.date.fromisoformat(selected['publishedAt'])<=asof)
    return {'versions':list(known.values()),'changes':changes,'pending':pending,'selected':requested,'selectedApplicable':eligible,
        'automaticRuleReplacement':False,'limitations':['适用性审阅为使用者声明，不代表自动法律认证','生效日和披露日分别记录，草案不得作为现行规则','规则差异不自动修改计算或旧快照']}

def cash(spec,nodes):
    s=copy.deepcopy(spec)
    if s.get('sameDayReleasedFundsUsable'):
        refs(s.get('sameDayAvailabilityEvidenceIds',[]),nodes)
        if not s.get('sameDayRuleReviewed'):raise ValueError('同日复用需要到账规则证据及明确核对')
    statuses=[]
    for issue in s['issues']:
        declarations=issue.pop('rateEvidence',None)
        if declarations is None:raise ValueError('新现金入口每只股票需rateEvidence；旧collision接口保留')
        graded=graded_allocation({'allocation':issue,'rateEvidence':declarations},nodes,spec.get('purpose','scenario'),spec.get('asOf'))
        if graded['status']!='calculated-conditional':return {'status':'blocked-missing-rate','code':issue['code'],'rateEvidence':graded['rateEvidence'],'daily':None}
        issue.update(graded['allocationSpec'])
        announced=issue.get('refundDate')
        if issue.get('factsStore'):
            from issuance_facts import view
            n=view({'code':issue['code'],'asOf':issue['asOf']},Path(issue['factsStore']))['facts']['refundDate']
            announced=n['value'] if n else announced
        available=issue.get('refundAvailableDate')
        if available:
            dt.date.fromisoformat(available)
            if available<announced:raise ValueError('实际可用日不能早于公告退款日')
            refs(issue.get('availabilityEvidenceIds',[]),nodes)
            if issue.get('factsStore'):
                resolved=calculate(issue)
                for key in ['price','maxShares','refundDate']:issue[key]=resolved['factEvidence'][key]['value']
                issue.pop('factsStore')
            issue['refundDate']=available
        statuses.append({'code':issue['code'],'announcedRefundDate':announced,'modeledAvailableDate':available or announced,
            'availabilityStatus':'supplied-account-or-broker-evidence' if available else 'announcement-date-scenario-not-certified-account-arrival'})
    result=collision(s);daily={}
    for label,scenario in result['scenarios'].items():
        grouped={}
        for row in scenario['ledger']:grouped.setdefault(row['date'],[]).append(row)
        start=dt.date.fromisoformat(min(grouped));end=dt.date.fromisoformat(max(grouped))
        if (end-start).days>3660:raise ValueError('每日现金账最多3660自然日')
        running=Decimal(result['totalFunds']);days=[]
        for offset in range((end-start).days+1):
            day=(start+dt.timedelta(days=offset)).isoformat();events=grouped.get(day,[]);opening=running
            low=min([opening]+[Decimal(r['cashAfter']) for r in events])
            if events:running=Decimal(events[-1]['cashAfter'])
            occupied=sum((Decimal(segment['capital']) for issue in result['issues'] for segment in issue['scenarios'][label]['segments'] if segment['start']<=day<segment['endExclusive']),Decimal(0))
            days.append({'date':day,'openingCash':str(opening),'closingCash':str(running),'intradayMinimumCash':str(low),
                'peakShortfall':str(max(Decimal(0),-low)),'occupiedPrincipal':str(occupied),'events':events})
        daily[label]=days
    return {'result':result,'dateEvidence':statuses,'daily':daily,'recommendation':None}

def counterfactual(spec,nodes):
    if spec.get('predictionPath'):
        from prediction_review import read
        p=Path(spec['predictionPath']);record=read(p)
        if record.get('type')!='bjx-prediction-record':raise ValueError('不是预测档案')
        for item in record['inputs']:
            if sha((p.parent/'inputs'/item['archiveName']).read_bytes())!=item['sha256']:raise ValueError('预测输入档案被修改')
        base=copy.deepcopy(record['allocationSpec'])
        if base.get('factsStore'):
            for key in ['price','maxShares','refundDate']:base[key]=record['prediction']['factEvidence'][key]['value']
            base.pop('factsStore')
        if spec.get('baseline') is not None:raise ValueError('使用首次档案时不得另行替换基线')
    else:base=copy.deepcopy(spec['baseline'])
    changes=spec.get('changes',[])
    if not changes or len(changes)>30:raise ValueError('需1至30个单因子变化')
    baseline=calculate(base);rows=[]
    allowed={'price','maxShares','budget','refundDate','saleSettlementDate','applyDate','ratesPct.P75','ratesPct.P50','ratesPct.P25'}
    # Resolve archived facts once, then keep inputs fixed across interventions.
    if base.get('factsStore'):
        for k in ['price','maxShares','refundDate']:base[k]=baseline['factEvidence'][k]['value']
        base.pop('factsStore')
    for c in changes:
        field=c['field'];category=c['category']
        if field not in allowed or category not in ['input','scope','rule','correction','calculation']:raise ValueError('反事实字段或差异类型不支持')
        refs(c.get('evidenceIds',[]),nodes)
        changed=copy.deepcopy(base);parts=field.split('.')
        if len(parts)==2:old=changed[parts[0]][parts[1]];changed[parts[0]][parts[1]]=c['value']
        else:old=changed[field];changed[field]=c['value']
        value=calculate(changed);delta={}
        for label in LABELS:
            delta[label]={}
            for metric in ['wholeLotShares','thresholdFunds','capitalDays','netProfit']:
                a=baseline['scenarios'][label][metric];b=value['scenarios'][label][metric]
                delta[label][metric]=str(Decimal(str(b))-Decimal(str(a))) if a is not None and b is not None else None
        rows.append({'field':field,'before':old,'after':c['value'],'category':category,'evidenceIds':c['evidenceIds'],'delta':delta,
            'interpretation':'固定其他输入的单因子敏感性；差异类别为输入声明，不证明因果'})
    comparable=bool(spec.get('sameRuleAndScope') is True and spec.get('verifiedFrozenSample') is True)
    return {'baseline':baseline,'interventions':rows,'declaredComparable':comparable,'eligibleForModelImprovement':False,
        'limitations':['单因子变化之和不等于多因子总变化，整数取整有非线性','规则替换只作为指定参数变化，不自动执行新法律规则','不回写首次预测，历史回放不证明模型改善']}

def matched_review(spec):
    from prediction_review import read,compare
    from research_evidence import verify
    groups=[];excluded=[]
    for group in ['before','after']:
        keep={}
        for item in spec.get(group,[]):
            try:
                review=read(item['reviewPath']);prediction=read(item['predictionPath'])
                verify(item['packagePath']);root=Path(item['packagePath']);manifest=load(root/'manifest.json')
                if review['predictionHash']!=prediction['recordHash']:raise ValueError('复盘与预测档案不匹配')
                if not review['eligibleForFrozenComparison'] or prediction['mode']!='first-live-capture':raise ValueError('非真实首次捕获')
                if manifest['mode']!='predecision' or timestamp(manifest['recordedAt'])>=timestamp(prediction['decisionCutoff']) or manifest['decisionCutoff']!=prediction['decisionCutoff']:raise ValueError('缺对应截止前快照包')
                for x in prediction['inputs']:
                    if sha((Path(item['predictionPath']).parent/'inputs'/x['archiveName']).read_bytes())!=x['sha256']:raise ValueError('冻结输入哈希不符')
                inputs=[x for x in manifest['dependencies'] if x['role']=='research-input']
                if len(inputs)!=1:raise ValueError('需唯一已打包研究输入')
                if inputs[0]['sha256'] not in {x['sha256'] for x in prediction['inputs']}:raise ValueError('快照研究输入不在首次冻结输入清单')
                research=load(root/inputs[0]['archive']);scope=research.get('comparisonScope')
                if not scope:raise ValueError('冻结输入缺少比较口径')
                rulefiles=sorted(x['sha256'] for x in manifest['dependencies'] if x['role']=='rule')
                if not rulefiles:raise ValueError('缺规则依赖')
                rule_state=research.get('rules',{})
                # Do not re-read mutable external evidence stores to certify old rules.
                archived_evidence=load(root/'evidence.json');assessment=rules({**rule_state,'asOf':research['asOf']},indexed(archived_evidence))
                if not assessment['selectedApplicable']:raise ValueError('冻结规则适用性未复核')
                key=(review['code'],review['decisionCutoff'])
                if key in keep:raise ValueError('模型组样本重复')
                keep[key]={'path':item['reviewPath'],'signature':sha(canonical({'scope':scope,'rulefiles':rulefiles,'selected':assessment['selected']}))}
            except (ValueError,KeyError,FileNotFoundError) as error:excluded.append({'group':group,'path':item.get('reviewPath'),'reason':str(error)})
        groups.append(keep)
    common=set(groups[0])&set(groups[1]);paired=[]
    for key in sorted(common):
        if groups[0][key]['signature']!=groups[1][key]['signature']:excluded.append({'sample':key,'reason':'规则或冻结口径不同'});continue
        paired.append(key)
    result=compare({name:[groups[index][key]['path'] for key in paired] for index,name in enumerate(['before','after'])})
    result['evidenceEligibilityExclusions']=excluded;result['eligibleForModelImprovement']=False
    result['limitations'].append('新增门禁核对冻结包、规则文件和冻结口径；本地时间及声明仍不构成外部认证')
    return result

def company_cards(path,code=None,asof=None):
    data=load(path)
    if data.get('type')!='bjx-company-research-card':raise ValueError('公司卡类型不符')
    if code is not None and data.get('code')!=code:raise ValueError('公司研究主体不同')
    if asof is not None and data.get('asOf')!=asof:raise ValueError('公司研究截止日与发行研究不一致，需重建对应版本')
    return {'financialQuality':{'financials':data['financials'],'gaps':data['gaps'],
            'auditOpinion':'not-extracted','restatementStatus':'requires-original-review','fraudVerdict':None},
        'peerComparability':{'period':data['valuation']['period'],'basis':'adjusted-FY-consolidated','peers':data['valuation']['peers'],
            'excludedPeers':data['valuation']['excludedPeers'],'median':data['valuation']['peerMedianPe'],'recommendation':None},
        'sourceResultSha256':sha(Path(path).read_bytes())}

def run(spec):
    if not spec.get('code') or not spec.get('asOf'):raise ValueError('研究需证券代码和截止日')
    if not re.fullmatch('[0-9]{6}',spec['code']):raise ValueError('证券代码须六位字符串')
    if spec.get('purpose','scenario') not in ['scenario','historical-review','predecision']:raise ValueError('研究用途无效')
    evidence=export(spec.get('evidence',{}));nodes=indexed(evidence);asof=dt.date.fromisoformat(spec['asOf'])
    if spec.get('evidence',{}).get('code') and spec['evidence']['code']!=spec['code']:raise ValueError('研究主体与事实库主体不同')
    if any(n.get('publishedAt') and dt.date.fromisoformat(n['publishedAt'][:10])>asof for n in nodes.values()):raise ValueError('证据晚于研究截止日')
    r={'type':'bjx-integrated-issuance-research','code':spec['code'],'asOf':spec['asOf'],'evidence':evidence,'fieldConflicts':conflicts(evidence),
        'riskNotice':'仅为发行研究与条件测算，不执行申购，不保证获配或收益','missingModules':[]}
    used=[]
    if spec.get('allocationResearch'):
        r['allocation']=graded_allocation(spec['allocationResearch'],nodes,spec.get('purpose','scenario'),spec['asOf'])
        if spec['allocationResearch']['allocation']['code']!=spec['code']:raise ValueError('获配测算主体不一致')
        used += [i for x in r['allocation']['rateEvidence'].values() for i in x.get('evidenceIds',[])]
        for metric,proof in r['allocation'].get('result',{}).get('factEvidence',{}).items():
            used += [n['id'] for n in nodes.values() if n['subject']==spec['code'] and n['metric']==metric and n.get('documentSha256')==proof['documentSha256'] and n.get('value')==proof['value']]
    for key,fn in [('structure',structure),('timeline',timeline),('rules',rules),('cash',cash),('counterfactual',counterfactual)]:
        if spec.get(key):r[key]=fn({**spec[key],'asOf':spec['asOf'],'purpose':spec.get('purpose','scenario')},nodes)
        else:r['missingModules'].append(key)
    if spec.get('evidence',{}).get('companyResult'):
        r['companyCards']=company_cards(spec['evidence']['companyResult'],spec['code'],spec['asOf'])
    else:r['missingModules'].append('companyCards')
    if spec.get('matchedReview'):r['matchedReview']=matched_review(spec['matchedReview'])
    r['panel']=panel({'code':spec['code'],'fields':spec.get('fields',DEFAULT_FIELDS),'usedEvidenceIds':list(set(used))},evidence)
    r['eligibleForModelImprovement']=False
    r['ruleApplicability']='reviewed-by-caller' if r.get('rules',{}).get('selectedApplicable') else 'not-confirmed-conditional-formula-only'
    return r

def snapshot(spec,result,input_path,result_path,workspace):
    evidence=result['evidence'];created=now().isoformat();deps=[{'path':str(input_path.resolve()),'role':'research-input'}, {'path':str(result_path.resolve()),'role':'calculation-result','availableAt':created}]
    # Archive code and configuration without depending on the author's installation paths.
    for name in ['issuance_research.py','research_evidence.py','issuance_facts.py','allocation_cash.py','company_research.py']:
        deps.append({'path':str(Path(__file__).with_name(name)),'role':'calculation-code','availableAt':created})
    if spec.get('allocationResearch',{}).get('allocation',{}).get('factsStore'):
        store=Path(spec['allocationResearch']['allocation']['factsStore'])
        for p in sorted((store/'research-data'/'bjx-facts'/spec['code']/'versions').glob('*.json')):
            if load(p)['publishedAt']<=spec['asOf']:deps.append({'path':str(p),'role':'facts-version'})
    deps.extend(spec.get('snapshot',{}).get('dependencies',[]))
    prediction_path=spec.get('counterfactual',{}).get('predictionPath')
    if prediction_path:
        from prediction_review import read
        p=Path(prediction_path);record=read(p);deps.append({'path':str(p),'role':'prediction-record'})
        deps.extend({'path':str(p.parent/'inputs'/x['archiveName']),'sha256':x['sha256'],'role':'prediction-input','availableAt':x['availableAt']} for x in record['inputs'])
    options=spec.get('snapshot',{})
    return package({'mode':options.get('mode','research'),'decisionCutoff':options.get('decisionCutoff'),
        'availabilityBySha256':options.get('availabilityBySha256',{}),'evidence':{'nodes':evidence['nodes']},
        'dependencies':deps+evidence['attachments']},workspace)

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['run','panel','rates','structure','timeline','rules','cash','counterfactual','matched-review']);p.add_argument('input',type=Path);p.add_argument('--workspace',type=Path,default=Path.cwd());p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():raise ValueError('输出已存在')
    s=load(a.input)
    if a.command=='run':r=run(s)
    elif a.command=='matched-review':r=matched_review(s)
    else:
        evidence=export(s.get('evidence',{}));nodes=indexed(evidence)
        if s.get('asOf') and any(n.get('publishedAt') and dt.date.fromisoformat(n['publishedAt'][:10])>dt.date.fromisoformat(s['asOf']) for n in nodes.values()):raise ValueError('证据晚于研究截止日')
        functions={'panel':lambda:panel(s,evidence),'rates':lambda:graded_allocation(s,nodes,s.get('purpose','scenario'),s.get('asOf')),
            'structure':lambda:structure(s,nodes),'timeline':lambda:timeline(s,nodes),'rules':lambda:rules(s,nodes),'cash':lambda:cash(s,nodes),'counterfactual':lambda:counterfactual(s,nodes)}
        r=functions[a.command]()
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open('x',encoding='utf-8') as f:json.dump(r,f,ensure_ascii=False,indent=2,allow_nan=False)
    if a.command=='run' and s.get('snapshot'):
        receipt=a.out.with_name(a.out.stem+'-snapshot.json')
        if receipt.exists():raise ValueError('快照回执已存在')
        result=snapshot(s,r,a.input,a.out,a.workspace)
        with receipt.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
if __name__=='__main__':main()
