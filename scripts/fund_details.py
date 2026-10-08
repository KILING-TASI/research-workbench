"""Unified third-party fund facts with explicit dates and gaps; no opaque ratings."""
import argparse,datetime as dt,json,re,math,hashlib,statistics
from pathlib import Path
from portable_collect import get,named
from research_pipeline import series
from fund_series_tools import day,NOTICE
from series_frequency import inspect as frequency_inspect
from collection_validation import unique_pairs,reject_constant

def extract(text,code,asof,retrieved):
    day(asof)
    if not isinstance(code,str) or not re.fullmatch(r'\d{6}',code) or str(named(text,'fS_code'))!=code or not isinstance(named(text,'fS_name'),str) or not named(text,'fS_name').strip():raise ValueError('基金身份不匹配')
    url='https://fund.eastmoney.com/pingzhongdata/'+code+'.js';hs=[]
    for h in named(text,'Data_netWorthTrend') or []:
        if not isinstance(h,dict):raise ValueError('净值结构变化')
        stamp=h.get('x')
        if isinstance(stamp,bool) or not isinstance(stamp,(int,float)) or not math.isfinite(stamp):raise ValueError('净值时间戳无效')
        d=dt.datetime.fromtimestamp(stamp/1000,dt.timezone(dt.timedelta(hours=8))).date().isoformat()
        if d<=asof:
            v=h['y']
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0:raise ValueError('无效单位净值')
            hs.append(dict(date=d,nav=v,distribution=h.get('unitMoney') or ''))
    if [x['date'] for x in hs]!=sorted(set(x['date'] for x in hs)):raise ValueError('历史重复或乱序')
    facts={};gaps=[]
    if hs:facts['latestNAV']=dict(value=hs[-1]['nav'],unit='unit-nav-currency-unverified',currency=None,currencyVerified=False,observedAt=hs[-1]['date'],sourceUrl=url,basis='third-party-unit-nav')
    else:gaps.append('截止日前无有效净值')
    if hs:gaps.append('净值币种未独立核实，不默认人民币；不可直接进行跨币种金额比较')
    for label,key in [('assetAllocation','Data_assetAllocation'),('holderStructure','Data_holderStructure')]:
        data=named(text,key)
        if not isinstance(data,dict):gaps.append(label+'缺失');continue
        categories=data.get('categories',[]);columns=data.get('series',[])
        if not isinstance(categories,list) or not isinstance(columns,list) or any(not isinstance(c,dict) for c in columns):raise ValueError('分类结构无效')
        for d in categories:day(d)
        if categories!=sorted(set(categories)):raise ValueError('分类日期重复或乱序')
        names=[c.get('name') for c in columns]
        if any(not isinstance(n,str) or not n.strip() for n in names) or len(set(names))!=len(names):raise ValueError('分类字段缺名或同名冲突')
        if any(not isinstance(c.get('data'),list) or len(c['data'])!=len(categories) for c in columns):raise ValueError('分类日期与数据长度不一致')
        observations=[]
        for i,d in enumerate(categories):
            day(d)
            if d>asof:continue
            values={}
            for col in columns:
                v=col['data'][i]
                if v is not None:
                    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):raise ValueError('分类数值异常')
                values[col['name']]=v
            observations.append(dict(date=d,values=values))
        if not observations or not columns:gaps.append(label+'截止日前无可用分类数据')
        facts[label]=dict(observations=observations,sourceUrl=url,basis='provider-reported-snapshot',unitNote='持有比例/占净比为百分数；净资产数值单位未独立核实，不转成元，不拼入规模排序',publicationVerified=False)
    # Current manager and fee snippets have no reliable historical validity date.
    current=named(text,'Data_currentFundManager') or []
    if not isinstance(current,list) or any(not isinstance(m,dict) for m in current):raise ValueError('经理线索结构无效')
    facts['managerClues']=dict(value=[dict(name=m.get('name'),roleVerified=False,reportedRole=None,providerId=m.get('id'),reportedExperience=m.get('workTime'),reportedManagedSize=m.get('fundSize')) for m in current],sourceUrl=url,retrievedAt=retrieved,basis='current-provider-clue-not-tenure-verification',historicalAsOfVerified=False)
    fees={k:named(text,k) for k in ['fund_sourceRate','fund_Rate','fund_minsg']}
    facts['holdingCodeClues']=dict(stockCodes=named(text,'stockCodes'),bondCodes=named(text,'zqCodes'),sourceUrl=url,basis='provider-code-clues-no-date-no-weights')
    facts['subscriptionClues']=dict(providerOriginalRate=fees['fund_sourceRate'],providerDiscountedRate=fees['fund_Rate'],providerMinimumAmount=fees['fund_minsg'],sourceUrl=url,retrievedAt=retrieved,basis='provider-channel-clue-not-contract-fee',historicalAsOfVerified=False)
    results=[]
    for months in [1,3,6,12,36]:
        cutoff=dt.date.fromisoformat(asof);m=cutoff.year*12+cutoff.month-1-months;y,m=divmod(m,12);m+=1
        import calendar
        start=dt.date(y,m,min(cutoff.day,calendar.monthrange(y,m)[1])).isoformat();rows=[h for h in hs if h['date']>=start]
        if len(rows)<2:results.append(dict(months=months,status='历史不足',requestedStart=start,metrics=None));continue
        start_gap=(dt.date.fromisoformat(rows[0]['date'])-dt.date.fromisoformat(start)).days
        end_gap=(cutoff-dt.date.fromisoformat(rows[-1]['date'])).days
        if start_gap>7 or end_gap>7:
            results.append(dict(months=months,requestedStart=start,start=rows[0]['date'],end=rows[-1]['date'],observations=len(rows),status='请求区间未覆盖：成立较晚、历史缺口或净值陈旧，暂不输出该阶段指标',startGapCalendarDays=start_gap,endGapCalendarDays=end_gap,boundaryToleranceCalendarDays=7,fullCalendarVerified=False,metrics=None));continue
        try:
            wealth=series(rows,asof,'nav-with-distributions');ds=list(wealth);values=list(wealth.values());returns=[b/a-1 for a,b in zip(values,values[1:])];peak=values[0];dd=0.
            for v in values:peak=max(peak,v);dd=max(dd,1-v/peak)
            years=(dt.date.fromisoformat(ds[-1])-dt.date.fromisoformat(ds[0])).days/365.25
            spacing=frequency_inspect(ds)
            metrics=dict(returnPct=(values[-1]/values[0]-1)*100,cagrPct=((values[-1]/values[0])**(1/years)-1)*100,annualVolatilityPct=statistics.stdev(returns)*math.sqrt(252)*100 if len(returns)>1 and spacing['dailyAnnualizationAllowed'] else None,maximumDrawdownPct=dd*100)
            if any(v is not None and not math.isfinite(v) for v in metrics.values()):raise ValueError('阶段指标超出有限数值范围')
            results.append(dict(months=months,requestedStart=start,start=ds[0],end=ds[-1],observations=len(ds),frequencyCheck=spacing,fullCalendarVerified=False,boundaryToleranceCalendarDays=7,startGapCalendarDays=start_gap,endGapCalendarDays=end_gap,metrics=metrics,eventVerification='provider-events-unverified',sourceUrl=url))
        except (ValueError,ArithmeticError) as e:results.append(dict(months=months,status='阶段计算未完成，需核对输入及事件：'+str(e),metrics=None))
    gaps+=['同类排名与可比同业池未取得','基金类型、成立日期与合同基准需原文或主数据核验','管理费、托管费及赎回阶梯需有效法律文件核验','持仓股票/债券仅代码线索，缺报告日权重及合计核对','经理任职起止、在管与历史产品清单需任职公告核验','规模金额单位与报告原文尚未核实']
    return dict(type='fund-details',code=code,name=named(text,'fS_name'),asOf=asof,retrievedAt=retrieved,sourceUrl=url,rawSha256=hashlib.sha256(text.encode('utf8')).hexdigest(),facts=facts,stagePerformance=results,distributionEvents=[x for x in hs if x['distribution']],gaps=gaps,riskNotice=NOTICE,limitations=['独立取数为第三方资料，不冒称官方核验；当前修订历史不是事前冻结数据','按净值所属日过滤，不证明历史披露日；经理和费率线索不作为历史截止日事实','252交易日年化是假设，交易日完整性未核验；短窗口几何年化不可当预期收益','收益按已记录分红理论再投，不保证事件无遗漏；现金分红需另走定投/事件工具','资产占净比可能因应收应付及杠杆不合计100%，不强行归一化；持有人内部占比不能与机构个人重复相加'])

def attach_manager_report(r, archive):
    """Re-read original PDF; keep period evidence separate from channel clues."""
    if archive.get('code') != r['code']: raise ValueError('经理报告基金代码不匹配')
    period=archive.get('reportDate'); published=archive.get('metadata',{}).get('publishedAt')
    day(period); day(published)
    if period > r['asOf'] or published > r['asOf']: raise ValueError('经理报告超过研究截止日')
    from report_manager_tenure import extract_archive
    evidence=extract_archive(archive)
    channel={m['name'] for m in r['facts'].get('managerClues',{}).get('value',[]) if m.get('name')}
    reported={m['name'] for m in evidence['managers']}
    evidence['channelNameComparison']=dict(channelOnly=sorted(channel-reported),reportOnly=sorted(reported-channel),shared=sorted(channel & reported),currentRoleConflictVerified=False)
    r['facts']['managerReportEvidence']=evidence
    return r

def attach_holdings_report(r, archive):
    """Attach reconciled report snapshots; verify retained original integrity."""
    if archive.get('code') != r['code']: raise ValueError('持仓报告基金代码不匹配')
    raw=Path(archive['documentPath']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=archive['sha256']:raise ValueError('持仓PDF哈希不一致')
    from report_screen_bridge import candidate
    evidence=candidate(archive,r['asOf'])
    r['facts']['reportEquityHoldings']=evidence['holdings']
    r['facts']['reportNetAssets']=evidence['fields']['aumCNY']
    replacements={
        '持仓股票/债券仅代码线索，缺报告日权重及合计核对':'报告期末完整股票表已核对；当前股票持仓、债券与衍生品明细仍未核验',
        '规模金额单位与报告原文尚未核实':'已取得报告期末全基金净资产（元）；渠道规模单位与当前规模仍未独立核验'}
    r['gaps']=[replacements.get(x,x) for x in r.get('gaps',[])]
    return r

def markdown(r):
    rows=['# '+r['name']+'：基金资料与历史表现','',f"基金代码{r['code']}，资料截止日{r['asOf']}。第三方数据，原文未完整核验。"]
    nav=r['facts'].get('latestNAV')
    if nav:rows.append(f"最新已取得单位净值{nav['value']}（币种尚未核实），所属日{nav['observedAt']}。")
    usable=[p for p in r['stagePerformance'] if p.get('metrics')]
    rows+=['','## 研究结论']
    if usable:
        selected=max(usable,key=lambda p:p['months']);m=selected['metrics']
        rows.append(f"本次可计算窗口中最长为{selected['months']}个月（{selected['start']}至{selected['end']}），区间收益{m['returnPct']:.2f}%，观测最大回撤{m['maximumDrawdownPct']:.2f}%。收益与回撤应同时看：这反映该段历史的获利和承压情况，不能单凭收益高低判定产品或经理优劣。")
        rows.append('目前可以回答已取得净值区间内的历史表现；尚不能建立完整基金评价。缺少可比同业和合同基准时，不能判断是否优于同类；分红事件、交易日完整性与币种未完整核验时，也不能把结果等同于真实账户收益。')
    else:
        rows.append('本次未形成可用阶段指标，暂不能评价历史收益风险。请先补齐请求区间净值并核对事件与端点；这不表示基金表现差。')
    rows+=['','|窗口|实际区间|收益率|最大回撤|年化波动|','|---|---|---:|---:|---:|']
    for p in r['stagePerformance']:
        m=p.get('metrics')
        if m:rows.append(f"|{p['months']}个月|{p['start']}至{p['end']}|{m['returnPct']:.2f}%|{m['maximumDrawdownPct']:.2f}%|{m['annualVolatilityPct'] if m['annualVolatilityPct'] is not None else '不足'}|")
        else:rows.append(f"|{p['months']}个月|{p.get('status','不足')}|—|—|—|")
    clue=r['facts'].get('managerClues')
    if clue:
        rows+=['','## 经理资料线索','以下为渠道返回的姓名，不是已核验的当前或历史任职名单。获取时间：'+str(clue.get('retrievedAt') or '原始归档未提供')+'。']
        names=[str(x['name']).replace('\n',' ') for x in clue.get('value',[]) if x.get('name')]
        rows.append('渠道姓名：'+('、'.join(names) if names else '未取得明确姓名')+'。')
        rows+=['响应未核验各姓名职务，多个姓名不自动表示共同管理。任职起止、经理身份及完整管理产品仍需公告原文；不能用本条网页线索替代历史截止日事实。','[经理资料渠道]('+clue['sourceUrl']+')']
    evidence=r['facts'].get('managerReportEvidence')
    if evidence:
        rows+=['','## 定期报告中的经理任职记录', '报告所属日'+evidence['reportDate']+'，披露日'+evidence['publishedAt']+'。已重新读取原PDF并核对文件摘要；该报告不能证明今天仍在任。']
        for m in evidence['managers']:
            rows.append(m['name']+'：任职起点'+m['start']+'；离任日期'+(m['end'] or '报告未披露')+'；记录确认至'+m['confirmedThrough']+'。'+m['locator']+'。')
            rows.append('原文职务：'+m['roleText']+'。 [报告原文]('+m['sourceUrl']+')')
        rows.append('另有经理助理记录'+str(len(evidence['assistantRecords']))+'条、职务歧义记录'+str(len(evidence['ambiguousRoleRecords']))+'条，未计入经理名单。')
        for category,label in [('assistantRecords','经理助理'),('ambiguousRoleRecords','职务待核对')]:
            for m in evidence[category]:
                rows.append(label+'：'+m['name']+'；原文职务：'+m['roleText']+'；'+m['locator']+'。 [报告原文]('+m['sourceUrl']+')')
        if not evidence['managers']: rows.append('未提取到可确认的经理行，不代表没有基金经理。')
        comparison=evidence.get('channelNameComparison',{})
        if comparison.get('channelOnly'):
            rows.append('渠道有、报告经理表未列出的姓名：'+'、'.join(comparison['channelOnly'])+'。资料时点不同且渠道职务未核验，不据此认定任职冲突或报告遗漏。')
        if comparison.get('reportOnly'):
            rows.append('报告有、渠道未返回的经理姓名：'+'、'.join(comparison['reportOnly'])+'。不能据此推断已经离任。')
        rows.append('PDF摘要：'+evidence['sourceSha256'])
    holdings=r['facts'].get('reportEquityHoldings')
    if holdings:
        rows+=['','## 已核对的报告股票持仓', '报告期末'+holdings['observedAt']+'，披露日'+holdings['publishedAt']+'；股票表完整，不代表当前持仓，亦不覆盖债券和衍生品。']
        aum=r['facts'].get('reportNetAssets')
        if aum:
            rows.append('同期全基金净资产'+format(aum['value'],',.2f')+'元；这是各份额合计规模，不是本份额规模或当前规模。')
        stocks=holdings['value'];total=sum(x['weightPct'] for x in stocks)
        rows.append('股票明细共'+str(len(stocks))+'项，占全基金净资产'+format(total,'.2f')+'%。剩余比例不直接视为现金。')
        rows+=['','|股票|市场|占净资产|原文位置|','|---|---|---:|---|']
        for x in sorted(stocks,key=lambda x:x['weightPct'],reverse=True):
            rows.append('|'+str(x['name']).replace('|','／')+' '+x['code']+'|'+x['market']+'|'+format(x['weightPct'],'.2f')+'%|'+str(x['locator']).replace('|','／')+'|')
        rows+=['','[持仓报告原文]('+holdings['sourceUrl']+')','PDF摘要：'+holdings['sourceSha256']]
    rows+=['','## 尚需核验或补充']+['- '+x for x in r['gaps']]+['','## 口径说明']+['- '+x for x in r['limitations']]+['',f"[净值及资料来源]({r['sourceUrl']})",r['riskNotice']]
    return '\n'.join(rows)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--code',required=True);p.add_argument('--as-of',required=True);p.add_argument('--raw',type=Path);p.add_argument('--manager-report',type=Path);p.add_argument('--holdings-report',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if not re.fullmatch(r'\d{6}',a.code):raise ValueError('六位基金代码')
    if a.out.exists() or a.out.with_suffix('.md').exists():raise ValueError('输出已存在')
    now=dt.datetime.now(dt.timezone.utc).isoformat();text=a.raw.read_text(encoding='utf-8-sig') if a.raw else get('https://fund.eastmoney.com/pingzhongdata/'+a.code+'.js');r=extract(text,a.code,a.as_of,None if a.raw else now);r['processedAt']=now
    if a.manager_report:attach_manager_report(r,json.loads(a.manager_report.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant))
    if a.holdings_report:attach_holdings_report(r,json.loads(a.holdings_report.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant))
    body=markdown(r);payload=json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False)
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(payload,encoding='utf8');a.out.with_suffix('.md').write_text(body,encoding='utf8')
