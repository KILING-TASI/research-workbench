"""Collect explicit fund candidates, align NAV windows, then screen."""
import argparse,datetime as dt,json,re,statistics,math,hashlib,uuid
from pathlib import Path
from portable_collect import get,named
from research_pipeline import series
from fund_details import extract
from multidimensional_screen import screen
from fund_series_tools import day,NOTICE
from series_frequency import inspect as frequency_inspect
from research_brief_html import render as render_html
from collection_validation import unique_pairs,reject_constant

def candidate_metrics(raws,start,end,rf=0):
    day(start);day(end)
    if start>=end or isinstance(rf,bool) or not isinstance(rf,(int,float)) or not math.isfinite(rf):raise ValueError('区间或无风险利率无效')
    parsed={};errors={}
    for code,text in raws.items():
        try:
            r=extract(text,code,end,None);rows=[]
            for h in named(text,'Data_netWorthTrend') or []:
                d=dt.datetime.fromtimestamp(h['x']/1000,dt.timezone(dt.timedelta(hours=8))).date().isoformat()
                if start<=d<=end:rows.append(dict(date=d,nav=h['y'],distribution=h.get('unitMoney') or ''))
            if len(rows)<3:raise ValueError('区间净值不足')
            if (dt.date.fromisoformat(rows[0]['date'])-dt.date.fromisoformat(start)).days>7 or (dt.date.fromisoformat(end)-dt.date.fromisoformat(rows[-1]['date'])).days>7:raise ValueError('净值未覆盖请求区间边界；成立晚或数据陈旧')
            wealth=series(rows,end,'nav-with-distributions');parsed[code]=(r,wealth)
        except (ValueError,KeyError,TypeError,OverflowError) as exc:errors[code]=str(exc)
    common=sorted(set.intersection(*(set(v[1]) for v in parsed.values()))) if parsed else []
    if len(common)<3:return [],dict(start=None,end=None,observations=len(common),errors=errors,reason='共同历史不足')
    spacing=frequency_inspect(common)
    candidates=[]
    for code,(r,wealth) in parsed.items():
        try:
            vals=[wealth[d] for d in common]
            if any(not math.isfinite(v) or v<=0 for v in vals):raise ValueError('对齐净值非有限或非正')
            rs=[b/a-1 for a,b in zip(vals,vals[1:])]
            if any(not math.isfinite(v) for v in rs):raise ValueError('收益序列溢出')
            vol=statistics.stdev(rs)*math.sqrt(252);peak=vals[0];dd=0
            for v in vals:peak=max(peak,v);dd=max(dd,1-v/peak)
            ar=statistics.mean(rs)*252
            values=dict(returnPct=(vals[-1]/vals[0]-1)*100,maximumDrawdownPct=dd*100,annualVolatilityPct=vol*100 if spacing['dailyAnnualizationAllowed'] else None,Sharpe=(ar-rf/100)/vol if vol and spacing['dailyAnnualizationAllowed'] else None)
            if any(v is not None and not math.isfinite(v) for v in values.values()):raise ValueError('派生指标溢出，不能用于筛选')
            fields={k:dict(value=v,observedAt=common[-1],window=common[0]+'/'+common[-1],sourceUrl=r['sourceUrl'],basis='provider-event-reinvest-aligned-daily-252',unit='ratio' if k=='Sharpe' else 'pct') for k,v in values.items()}
            candidates.append(dict(code=code,kind='fund',market='CN-fund',name=r['name'],fields=fields))
        except (ValueError,TypeError,OverflowError,ArithmeticError) as exc:errors[code]='指标计算未完成：'+str(exc)
    return candidates,dict(start=common[0],end=common[-1],observations=len(common),frequencyCheck=spacing,errors=errors,requestedStart=start,requestedEnd=end,calendarVerified=False,annualRiskFreePct=rf,limitations=['共同观测不证明无缺交易日；若缺日，将多日变化按单期计算可能改变波动','分红为供应商记录，尚非完整官方事件核验','夏普采用日收益算术年化超额除年化波动，不用CAGR代替均值'])

def summary(result,candidates):
    labels={'returnPct':'区间收益率','maximumDrawdownPct':'历史最大回撤','annualVolatilityPct':'年化波动率','Sharpe':'夏普比率'}
    def cell(value):return str(value).replace('|','／').replace('\n',' ')
    aligned=result['alignment'];lines=['# 基金池条件研究','',f"本次研究{result['candidateCount']}只基金：满足条件{len(result['selected'])}只，不满足{len(result['excluded'])}只，资料不足{len(result['unknown'])}只。",f"请求区间{aligned.get('requestedStart','未取得')}至{aligned.get('requestedEnd','未取得')}；共同区间{aligned.get('start') or '未取得'}至{aligned.get('end') or '未取得'}，{aligned['observations']}个观测。",'满足条件只表示符合本次历史指标阈值，不代表适合投资。','']
    lookup={c['code']:c for c in candidates}
    lines+=['## 逐只基金结果','| 基金 | 代码 | 结果 | 区间收益率 | 历史最大回撤 | 年化波动率 | 夏普比率 |','| --- | --- | --- | ---: | ---: | ---: | ---: |']
    for key,label in [('selected','满足条件'),('excluded','不满足条件'),('unknown','资料不足')]:
        for row in result[key]:
            fields=lookup[row['code']].get('fields',{});values=[]
            for name in labels:
                v=fields.get(name,{}).get('value');values.append('未取得' if v is None else f"{v:.2f}"+('' if name=='Sharpe' else '%'))
            lines.append('| '+' | '.join([cell(row.get('name') or row['code']),row['code'],label,*values])+' |')
    lines+=['','## 条件未通过或资料不足的原因']
    for row in result['excluded']+result['unknown']:
        for check in row['checks']:
            if check['passed'] is not True:lines.append('- '+row['code']+'：'+check['reason'])
    lines+=['','## 本次筛选条件']
    ops={'lt':'小于','le':'不超过','gt':'大于','ge':'不低于','eq':'等于'}
    for rule in result['conditions']:
        if rule['kind']=='metric':lines.append('- '+labels.get(rule['field'],rule['field'])+' '+ops[rule['op']]+' '+str(rule['value']))
        else:lines.append('- '+cell(rule))
    lines+=['','## 可比排序结果']
    if not result.get('rankingGroups'):lines.append('本次未形成可比排序组：未指定排序或排序字段不足。')
    for index,group in enumerate(result.get('rankingGroups',[]),1):
        observed,basis,window,unit,tracking=group['comparisonBasis']
        lines += ['',f'第{index}组：资料日期{observed}；统计区间{window or "未指定"}；单位{unit or "未指定"}。','不同组不能直接比较名次；此排序不代表同类权威排名或未来表现。','| 组内序号 | 基金 | 代码 | 排序字段值 |','| ---: | --- | --- | ---: |']
        for order,row in enumerate(group['rows'],1):
            name=lookup[row['code']].get('name') or row['code']
            lines.append('| '+str(order)+' | '+cell(name)+' | '+row['code']+' | '+format(row['value'],'.4f')+' |')
    for gap in result.get('rankingGaps',[]):lines.append('- '+gap['code']+'未进入排序：'+gap['reason'])
    lines+=['','## 资料与口径限制']
    lines += ['- '+c+'：'+x['reason'] for c,x in result['collection'].items() if x['status']=='failed']
    lines += ['- '+c+'：'+x for c,x in aligned['errors'].items()]
    lines += ['- '+x for x in aligned.get('limitations',[])]
    if aligned.get('reason'):lines.append('- '+aligned['reason'])
    lines += ['候选池未经风格分组，不能把不同类型当同类排名。评级、风险等级及主题数据没有来源时留空。','分红为供应商记录，复权事件尚未完成官方原文核验。','', '## 数据来源']
    lines += ['- '+c+'：'+x['sourceUrl'] for c,x in result['collection'].items() if x.get('sourceUrl')]
    lines += ['',NOTICE]
    return '\n'.join(lines)

def preserve_previous_outputs(outdir):
    names=['collection.json','screen-input.json','result.json','筛选简报.md','筛选简报.html']
    contents={}
    for name in names:
        path=outdir/name
        if not path.is_file():continue
        if path.stat().st_size>30*1024*1024:raise ValueError('历史输出单文件超过30MB，先人工归档再续采')
        contents[name]=path.read_bytes()
    if not contents:return None
    for raw in contents.values():
        if len(raw)>30*1024*1024:raise ValueError('历史输出单文件超过30MB，先人工归档再续采')
    version=outdir/'versions'/('before-resume-'+uuid.uuid4().hex);version.mkdir(parents=True,exist_ok=False)
    for name,raw in contents.items():(version/name).write_bytes(raw)
    manifest={'scope':'续采前存在的输出原样留存，不认证旧结果正确性或完整性','files':{name:hashlib.sha256(raw).hexdigest() for name,raw in contents.items()}}
    (version/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    return {'path':str(version.relative_to(outdir)),'manifestSha256':hashlib.sha256((version/'manifest.json').read_bytes()).hexdigest()}

def run(spec,outdir,resume=False,fetch=get):
    if not isinstance(spec,dict) or not isinstance(spec.get('codes'),list):raise ValueError('批量筛选请求须包含代码数组')
    rf=spec.get('annualRiskFreePct',0)
    if isinstance(rf,bool) or not isinstance(rf,(int,float)) or not math.isfinite(rf):raise ValueError('无风险利率须为有限数值')
    codes=spec['codes']
    if not codes or len(codes)>500 or len(set(codes))!=len(codes) or any(not isinstance(c,str) or not re.fullmatch(r'\d{6}',c) for c in codes):raise ValueError('需1至500个唯一六位基金代码')
    day(spec['start']);day(spec['end']);day(spec['asOf'])
    if spec['start']>=spec['end'] or spec['end']>spec['asOf']:raise ValueError('日期范围无效')
    pre=dict(asOf=spec['asOf'],candidates=[dict(code='validation',kind='fund',market='CN',fields={})],conditions=spec['conditions'])
    if spec.get('rank'):pre['rank']=spec['rank']
    screen(pre)
    outdir=Path(outdir);statefile=outdir/'collection.json'
    if outdir.exists() and not resume:raise ValueError('目录存在，续采须resume')
    outdir.mkdir(parents=True,exist_ok=True)
    state={'request':spec,'items':{}}
    if resume:
        if not statefile.exists():raise ValueError('无可续采记录')
        state=json.loads(statefile.read_text(encoding='utf8'),object_pairs_hook=unique_pairs,parse_constant=reject_constant)
        if not isinstance(state,dict) or not isinstance(state.get('items'),dict):raise ValueError('续采记录结构无效')
        if state['request']!=spec:raise ValueError('续采参数变化，请用新目录')
        if not isinstance(state.get('previousOutputVersions',[]),list):raise ValueError('续采历史版本记录须为数组')
        previous=preserve_previous_outputs(outdir)
        if previous:state.setdefault('previousOutputVersions',[]).append(previous)
    raws={}
    def save():
        tmp=statefile.with_suffix('.tmp');tmp.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf8');tmp.replace(statefile)
    for code in codes:
        cache=outdir/(code+'.js');item=state['items'].get(code,{})
        if item.get('status')=='downloaded' and cache.exists():
            raw=cache.read_bytes();text=raw.decode('utf8')
            if hashlib.sha256(raw).hexdigest()!=item.get('sha256'):raise ValueError('续采缓存哈希变化，请用新目录重取')
            raws[code]=text;continue
        try:
            text=fetch('https://fund.eastmoney.com/pingzhongdata/'+code+'.js');extract(text,code,spec['asOf'],None)
            cache.write_bytes(text.encode('utf8'));raws[code]=text;state['items'][code]=dict(status='downloaded',sha256=hashlib.sha256(text.encode('utf8')).hexdigest(),sourceUrl='https://fund.eastmoney.com/pingzhongdata/'+code+'.js',retrievedAt=dt.datetime.now(dt.timezone.utc).isoformat())
        except Exception as exc:state['items'][code]=dict(status='failed',reason=str(exc))
        save()
    candidates,alignment=candidate_metrics(raws,spec['start'],spec['end'],spec.get('annualRiskFreePct',0))
    # Failed/insufficient objects remain explicit unknown candidates rather than disappearing.
    existing={x['code'] for x in candidates}
    for c in codes:
        if c not in existing:candidates.append(dict(code=c,kind='fund',market='CN-fund',name=c,fields={}))
    conditions=[dict(rule) for rule in spec['conditions']]
    for rule in conditions:
        if rule.get('kind')=='metric' and rule.get('field') in {'returnPct','maximumDrawdownPct','annualVolatilityPct','Sharpe'}:
            declarations={(v['basis'],v['window']) for row in candidates if (v:=row.get('fields',{}).get(rule['field']))}
            if len(declarations)==1:
                basis,window=next(iter(declarations));rule.setdefault('basis',basis);rule.setdefault('window',window)
    s=dict(asOf=spec['asOf'],scope='用户指定基金池；不是全市场或同类权威排名',candidates=candidates,conditions=conditions)
    if spec.get('rank'):s['rank']=spec['rank']
    alignment.setdefault('requestedStart',spec['start']);alignment.setdefault('requestedEnd',spec['end'])
    result=screen(s);result['alignment']=alignment;result['collection']=state['items']
    text=summary(result,candidates);html=render_html(text)
    (outdir/'screen-input.json').write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf8');(outdir/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');save()
    alignment.setdefault('requestedStart',spec['start']);alignment.setdefault('requestedEnd',spec['end'])
    (outdir/'筛选简报.md').write_text(text,encoding='utf8');(outdir/'筛选简报.html').write_text(html,encoding='utf8');return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out-dir',type=Path,required=True);p.add_argument('--resume',action='store_true');a=p.parse_args();run(json.loads(a.input.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant),a.out_dir,a.resume)
