"""Manager-centric disclosed product/tenure registry, not a full career database."""
import argparse,json
from pathlib import Path
from fund_evaluation import evaluate
from research_brief_html import render as render_html
from fund_series_tools import day,source,NOTICE

def build(s):
    if not isinstance(s,dict):raise ValueError('经理产品输入须为对象')
    asof=day(s['asOf']);query=s.get('managerName');products=s['products']
    if query is not None and (not isinstance(query,str) or not query.strip()):raise ValueError('经理姓名筛选须为非空文字或未指定')
    if not isinstance(products,list) or not products or len(products)>500 or any(not isinstance(product,dict) for product in products):raise ValueError('需1至500份产品任职资料')
    records=[];seen=set();gaps=[]
    for product in products:
        issuer=product.get('managerCompany');spec=product['evaluationInput']
        if not isinstance(issuer,str) or not issuer.strip() or not isinstance(spec,dict) or spec['asOf']!=asof:raise ValueError('须经理公司及共同截止日')
        if not spec.get('managers'):gaps.append(dict(code=spec['code'],reason='任职记录缺失'));continue
        evaluated=evaluate(spec)
        for period,original in zip(evaluated['managerPeriods'],spec['managers']):
            if query and original['name']!=query:continue
            # Caller can bind an official person identifier; otherwise keep company/name resolution explicit.
            identity=product.get('managerIdentities',{}).get(original['name'])
            if identity:
                if not identity.get('id'):raise ValueError('经理身份标识缺失')
                source(identity['sourceUrl']);key=identity['id'];method='explicit-person-id-with-source'
            else:key=issuer+'::'+original['name'];method='name-and-company-not-global-person-id'
            dedup=(key,spec['code'],original['start'],original.get('end'),original['confirmedThrough'])
            if dedup in seen:raise ValueError('重复任职记录，不能重复计算')
            seen.add(dedup)
            end=original.get('end');confirmed=original['confirmedThrough']
            status='已披露离任' if end and end<=asof else '截止日在任已确认' if confirmed==asof else '仅确认至报告期，当前在管待核验'
            records.append(dict(managerKey=key,managerName=original['name'],identityMethod=method,identitySource=identity.get('sourceUrl') if identity else None,company=issuer,code=spec['code'],productName=product.get('name',spec['code']),reportedStart=original['start'],reportedEnd=end,confirmedThrough=confirmed,publishedAt=original['publishedAt'],sourceUrl=original['sourceUrl'],locator=original['locator'],currentStatus=status,performance=period))
    groups={}
    for r in records:groups.setdefault(r['managerKey'],[]).append(r)
    managers=[];conflicts=[]
    for key,rs in groups.items():
        for code in {r['code'] for r in rs}:
            versions=[r for r in rs if r['code']==code]
            starts={r['reportedStart'] for r in versions};ends={r['reportedEnd'] for r in versions if r['reportedEnd']}
            conflicting_open=any(not r['reportedEnd'] and any(r['confirmedThrough']>end for end in ends) for r in versions)
            if len(starts)>1 or len(ends)>1 or conflicting_open:
                conflicts.append(dict(managerKey=key,code=code,reason='任职起止记录冲突；可能分段任职或源差异，不能静默合并'))
                for v in versions:v['currentStatus']='任职记录冲突，需复核'
        intervals=sorted([(r['reportedStart'],r['reportedEnd'] or r['confirmedThrough']) for r in rs if r['currentStatus']!='任职记录冲突，需复核']);merged=[]
        for a,b in intervals:
            if merged and a<=merged[-1][1]:merged[-1][1]=max(merged[-1][1],b)
            else:merged.append([a,b])
        managers.append(dict(key=key,name=rs[0]['managerName'],products=rs,knownManagementIntervals=merged,knownProductCount=len({r['code'] for r in rs}),knownProductCountBasis='distinct-fund-codes-not-independent-strategies',careerComplete=False,currentListComplete=False,earliestKnownAppointment=min((a for a,b in intervals),default=None),knownCodeCount=len({r['code'] for r in rs}),strategyCount=None))
    return dict(type='manager-product-registry',asOf=asof,query=query,scope='已提供公开任职证据，不是经理全职业履历',managers=managers,conflicts=conflicts,gaps=gaps,riskNotice=NOTICE,limitations=['证券从业年限、基金管理年限、单产品任职年限分别核对，不用最早产品日期代替从业起点','姓名与公司仅为候选身份解析；跨公司同名不自动合并，明确标识需来源','旧报告确认的任职不自动延长到今日；产品清单不保证完整','同一基金A/C可能共享策略，不按份额数声称管理产品数量或重复加总业绩','共同管理区间只展示产品表现，不分配个人贡献；不同产品收益不加总为经理收益','不同起止/基准/风格的任职表现不作直接优劣排名'])

def markdown(r):
    def cell(value):return str(value).replace('|','／').replace('\n',' ')
    out=['# 基金经理与产品任职研究','',f"截止日{r['asOf']}。仅覆盖已取得公开证据，不是完整职业履历。"]
    if not r['managers']:out += ['', '已提供的资料中未找到匹配任职记录；这不代表该经理没有管理产品。']
    for m in r['managers']:
        earliest=m['earliestKnownAppointment'] or '因任职记录冲突暂不汇总'
        companies=sorted({p['company'] for p in m['products']})
        identity_methods=sorted({p['identityMethod'] for p in m['products']})
        out+=['','## '+cell(m['name']),'所属公司（按本次资料）：'+cell('、'.join(companies))+'。','身份匹配方式：'+cell('、'.join(identity_methods))+'；姓名与公司匹配仍不等于完整职业身份核验。',f"最早已知无冲突产品任职记录：{earliest}；这不是证券从业起点。",f"已知{m['knownCodeCount']}个基金代码，尚未合并A/C等共享策略份额，不能作为独立策略数量。",'','| 产品 | 报告任职起点 | 离任日期 | 确认至 | 状态 |','| --- | --- | --- | --- | --- |']
        for p in m['products']:
            out.append('| '+' | '.join(cell(x) for x in [p['code']+' '+p['productName'],p['reportedStart'],p['reportedEnd'] or '未披露离任',p['confirmedThrough'],p['currentStatus']])+' |')
        for p in m['products']:
            out+=['','### '+cell(p['code']+' '+p['productName'])]
            perf=p['performance'];metric=perf.get('metrics')
            if p['currentStatus']=='任职记录冲突，需复核':out.append('任职起止存在冲突；单份资料计算值不能用于确定经理任期表现。')
            if metric:out.append(f"按本条资料可计算区间为{perf['actualStart']}至{perf['actualEnd']}，累计收益{metric['totalReturnPct']:.2f}%，最大回撤{metric['maximumDrawdownPct']:.2f}%。这是产品表现，不等同于经理个人贡献。")
            else:out.append('任职区间历史不足，未输出业绩。')
            overlaps=perf.get('coManagementIntervals',[])
            if overlaps:
                out.append('本条已知共同管理区间如下；这些区间的产品收益不能归为该经理单独贡献，也不能把两位经理的任期收益相加。')
                for overlap in overlaps:
                    out.append('- '+cell(overlap['name'])+'：'+overlap['start']+'至'+overlap['end']+'；[共同管理任职资料]('+overlap.get('sourceUrl',p['sourceUrl'])+')，'+cell(overlap.get('locator',p['locator']))+'。')
            else:out.append('已提供任职资料中未检出共同管理交集；名单可能不完整，不能据此确认全程独立管理。')
            if metric and not perf.get('fullTenureCovered'):out.append('历史序列未覆盖完整报告任期；上述指标只对应实际可计算区间。')
            out.append(f"[任职资料]({p['sourceUrl']})，{cell(p['locator'])}。")
    out += ['', '## 冲突与资料缺口']
    if not r['conflicts'] and not r['gaps']:out.append('本次输入中未检出任职冲突或缺失；不代表产品名单完整。')
    for row in r['conflicts']+r['gaps']:out.append('- '+row['code']+'：'+row['reason'])
    out+=['','## 边界说明']+['- '+x for x in r['limitations']]+['',r['riskNotice']]
    return '\n'.join(out)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();r=build(json.loads(a.input.read_text(encoding='utf-8-sig')))
    if a.out.exists() or a.out.with_suffix('.md').exists() or a.out.with_suffix('.html').exists():raise ValueError('输出已存在')
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8');a.out.with_suffix('.md').write_text(markdown(r),encoding='utf8');a.out.with_suffix('.html').write_text(render_html(markdown(r)),encoding='utf8')
