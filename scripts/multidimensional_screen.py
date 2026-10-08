"""Evidence-bound screening, holdings reverse lookup and comparable ranking."""
import argparse,json,math
from pathlib import Path
from fund_series_tools import day,source,num,NOTICE
from research_brief_html import render as render_html
FIELDS={'fundType','inceptionYears','rating','riskLevel','returnPct','maximumDrawdownPct','annualVolatilityPct','Sharpe','dcaReturnPct','aumCNY','turnoverPct','netFlowCNY','valuationPercentile','valueExposure','growthExposure','sizeExposure'}
UNITS={**{f:'pct' for f in ['returnPct','maximumDrawdownPct','annualVolatilityPct','dcaReturnPct','turnoverPct','valuationPercentile']},'aumCNY':'CNY','netFlowCNY':'CNY','Sharpe':'ratio','inceptionYears':'years'}
OPS={'lt':lambda a,b:a<b,'le':lambda a,b:a<=b,'gt':lambda a,b:a>b,'ge':lambda a,b:a>=b,'eq':lambda a,b:a==b}

def evidence(v,asof):
    source(v['sourceUrl']);day(v['observedAt'])
    if 'sourceUrls' in v:
        urls=v['sourceUrls']
        if not isinstance(urls,list) or not urls or any(not isinstance(x,str) for x in urls) or v['sourceUrl'] not in urls:raise ValueError('多来源须为非空链接列表并包含主要来源')
        for url in urls:source(url)
    if v['observedAt']>asof or not isinstance(v.get('basis'),str) or not v['basis'].strip():raise ValueError('证据日期晚于截止日或缺少明确文字口径')
    if 'publishedAt' in v:
        day(v['publishedAt'])
        if v['publishedAt']>asof:raise ValueError('来源在截止日后披露')

def check(row,rule,asof):
    kind=rule['kind']
    if kind=='metric':
        field=rule['field'];v=row.get('fields',{}).get(field)
        if not v or v.get('value') is None:return None,'指标缺失'
        evidence(v,asof)
        if field=='netFlowCNY' and (not rule.get('basis') or not rule.get('window')):return None,'资金流条件须指定测算口径与统计区间，不能混用'
        expected=rule.get('unit',UNITS.get(field))
        if expected and v.get('unit')!=expected:return None,'指标单位缺失或不匹配；不自动换算'
        if field in {'returnPct','maximumDrawdownPct','annualVolatilityPct','Sharpe','dcaReturnPct'} and (not rule.get('basis') or not rule.get('window')):return None,'收益风险条件须明确收益口径与统计区间；不混用价格、净值或不同期间'
        if rule.get('basis') and rule['basis']!=v['basis']:return None,'指标口径不匹配'
        if rule.get('window') and rule['window']!=v.get('window'):return None,'统计区间不匹配'
        value=v['value'];op=rule['op'];threshold=rule['value']
        if op!='eq' or field in UNITS:num(value);num(threshold)
        return OPS[op](value,threshold),'指标比较'
    if kind=='tag':
        v=row.get('tags',{}).get(rule['dimension'])
        if not v:return None,'主题/行业/风格标签未取得'
        evidence(v,asof)
        if not isinstance(v['value'],list):raise ValueError('标签须列表')
        if rule.get('basis') and rule['basis']!=v['basis']:return None,'标签来源口径不匹配'
        return rule['value'] in v['value'],'标签匹配；不是未来表现判断'
    h=row.get('holdings')
    if not h:return None,'持仓未取得'
    evidence(h,asof)
    if h['basis'] not in ('actual-fund-holdings','verified-feeder-equity-lookthrough'):return None,'指数成分不能代替基金实际持仓'
    if h['basis']=='verified-feeder-equity-lookthrough' and h.get('complete') is True:raise ValueError('局部联接穿透不能标为完整持仓')
    namespaces=h.get('coveredSecurityNamespaces')
    if namespaces is not None:
        if not isinstance(namespaces,list) or not namespaces or any(not isinstance(x,str) or not x for x in namespaces):raise ValueError('披露证券命名空间须非空列表')
        if rule['market'] not in namespaces:return None,'查询证券不在本次披露资产范围内，不能据股票表判断债券或其他资产'
    elif h.get('scope')=='completeEquity' and rule['market'] not in ('CN-equity','HK-equity','US-equity','SSE','SZSE','HK','NASDAQ','NYSE'):
        return None,'本次仅完整股票披露，查询资产范围不匹配'
    matching=[x for x in h['value'] if x['code']==rule['code'] and x['market']==rule['market']]
    if not matching:
        return (False,'完整披露中未持有') if h.get('complete') is True else (None,'局部披露未出现，不能证明未持有')
    weight=sum(num(x['weightPct']) for x in matching)
    if h['basis']=='verified-feeder-equity-lookthrough' and weight<rule.get('minimumWeightPct',0):return None,f'已核验股票路径权重{weight:.6f}%，未展开部分可能另有暴露，不能判定低于阈值'
    return weight>=rule.get('minimumWeightPct',0),f'披露权重{weight:.6f}%；仅报告日快照'

def validate_rules(rules):
    if not isinstance(rules,list) or not rules:raise ValueError('筛选条件须非空列表')
    for rule in rules:
        if not isinstance(rule,dict):raise ValueError('筛选条件须对象')
        if rule.get('kind') not in ('metric','tag','holding'):raise ValueError('条件类型无效')
        if rule['kind']=='metric':
            if rule.get('field') not in FIELDS or rule.get('op') not in OPS:raise ValueError('指标或运算符不支持')
            if rule.get('op')!='eq' or rule['field'] in UNITS:num(rule['value'])
            if rule['field'] in UNITS and rule.get('unit',UNITS[rule['field']])!=UNITS[rule['field']]:raise ValueError('条件单位不符合字段规范，须先明确换算')
        if rule['kind']=='tag' and rule.get('dimension') not in ('theme','industry','style'):raise ValueError('标签维度无效')
        if rule['kind']=='holding' and (not rule.get('code') or not rule.get('market') or num(rule.get('minimumWeightPct',0))<0):raise ValueError('持仓证券须代码/市场与非负阈值')

def screen(s):
    asof=day(s['asOf']);rows=s['candidates'];rules=s['conditions']
    if not rows or len(rows)>5000 or not rules:raise ValueError('需1至5000个候选及非空条件')
    ids=[(r['kind'],r['market'],r['code']) for r in rows]
    if len(set(ids))!=len(ids):raise ValueError('同市场同品种候选重复')
    validate_rules(rules)
    selected=[];excluded=[];unknown=[];coverage=[];all_checks=[]
    for row in rows:
        checks=[]
        for rule in rules:
            try:passed,reason=check(row,rule,asof)
            except (ValueError,KeyError,TypeError) as exc:passed,reason=None,'该条件证据不可核验：'+str(exc)
            checks.append(dict(condition=rule,passed=passed,reason=reason))
        all_checks.append(checks)
        record={k:row.get(k) for k in ('code','kind','market','name')};record['checks']=checks
        if any(c['passed'] is False for c in checks):excluded.append(record)
        elif any(c['passed'] is None for c in checks):unknown.append(record)
        else:selected.append(record)
    for i,rule in enumerate(rules):coverage.append(dict(condition=rule,usable=sum(checks[i]['passed'] is not None for checks in all_checks),total=len(rows)))
    ranking=[];rankingGaps=[];rank=s.get('rank')
    if rank:
        if rank.get('field') not in FIELDS or rank.get('direction') not in ('asc','desc'):raise ValueError('排序参数无效')
        groups={};kept={(x['kind'],x['market'],x['code']) for x in selected}
        for row in rows:
            if (row['kind'],row['market'],row['code']) not in kept:continue
            if rank.get('sameIndexOnly') and not row.get('trackingIndex'):
                rankingGaps.append(dict(code=row['code'],reason='跟踪指数身份未取得，不能进入同指数排序'));continue
            v=row.get('fields',{}).get(rank['field'])
            if not v or v.get('value') is None:
                rankingGaps.append(dict(code=row['code'],reason='排序指标缺失'));continue
            if rank['field'] in {'returnPct','maximumDrawdownPct','annualVolatilityPct','Sharpe','dcaReturnPct','netFlowCNY'} and (not isinstance(v.get('window'),str) or not v['window'].strip()):
                rankingGaps.append(dict(code=row['code'],reason='排序统计区间未明确，不能把不同或未知区间混排'));continue
            expected=UNITS.get(rank['field'])
            if expected and v.get('unit')!=expected:
                rankingGaps.append(dict(code=row['code'],reason='排序指标单位缺失或不匹配'));continue
            try:evidence(v,asof);num(v['value'])
            except (ValueError,KeyError,TypeError) as exc:
                rankingGaps.append(dict(code=row['code'],reason='排序证据不可核验：'+str(exc)));continue
            signature=json.dumps([v['observedAt'],v['basis'],v.get('window'),v.get('unit'),row.get('trackingIndex') if rank.get('sameIndexOnly') else None],ensure_ascii=False,sort_keys=True)
            groups.setdefault(signature,[]).append(dict(code=row['code'],market=row['market'],kind=row['kind'],value=v['value'],sourceUrl=v['sourceUrl']))
        for sig,items in groups.items():ranking.append(dict(comparisonBasis=json.loads(sig),rows=sorted(items,key=lambda x:x['value'],reverse=rank['direction']=='desc')))
    return dict(type='multidimensional-screen',asOf=asof,scope=s.get('scope','指定输入候选池'),candidateCount=len(rows),conditions=rules,selected=selected,excluded=excluded,unknown=unknown,coverage=coverage,rankingGroups=ranking,rankingGaps=rankingGaps,riskNotice=NOTICE,limitations=['目录数量不等于七维数据覆盖；仅输入池，缺项不算通过','主题、评级、风险等级、因子暴露须已有证据，不按名称猜测；评级标准日期须写入口径','持仓为披露快照；局部报告缺证券不代表没有持有；指数成分不冒充基金持仓','资金流须标明供应商或份额测算口径；成交金额不是净流入','排序隔离日期、窗口、口径和单位；可选择同指数组，不跨组综合优选','定投表现依赖方案口径，年限和风险评级不构成收益保证'])

def markdown(result,spec):
    labels={'returnPct':'区间收益率','maximumDrawdownPct':'历史最大回撤','annualVolatilityPct':'年化波动率','Sharpe':'夏普比率','aumCNY':'基金净资产','netFlowCNY':'资金流字段','valuationPercentile':'估值历史分位','turnoverPct':'换手率','growthExposure':'成长暴露','valueExposure':'价值暴露','sizeExposure':'规模暴露','inceptionYears':'成立年限','riskLevel':'风险等级','rating':'评级','fundType':'基金类型','dcaReturnPct':'历史定投收益率'}
    def safe(value):return str(value).replace('|','／').replace('\n',' ')
    def links(ev):
        urls=ev.get('sourceUrls',[ev.get('sourceUrl')])
        if not isinstance(urls,list):urls=[ev.get('sourceUrl')]
        valid=[]
        for url in urls:
            try:source(url)
            except (ValueError,TypeError):continue
            valid.append(url)
        return valid
    def display(value,unit):
        if isinstance(value,(float,int)) and not isinstance(value,bool):
            text=f'{value:.4f}'.rstrip('0').rstrip('.')
        else:text=safe(value)
        return text+{'pct':'%','CNY':' 元','years':' 年','ratio':''}.get(unit,'')
    def describe(rule):
        if rule['kind']=='holding':return '持仓包含'+rule['market']+' '+rule['code']+'，披露权重不低于'+str(rule.get('minimumWeightPct',0))+'%'
        if rule['kind']=='tag':return {'theme':'主题','industry':'行业','style':'风格'}[rule['dimension']]+'标签包含'+str(rule['value'])
        op={'gt':'大于','ge':'不低于','lt':'小于','le':'不超过','eq':'等于'}[rule['op']]
        return labels[rule['field']]+op+display(rule['value'],rule.get('unit',UNITS.get(rule['field'])))+(('；统计区间'+rule['window']) if rule.get('window') else '')
    lines=['# 多维条件研究','',result['scope'],f"资料截止日{result['asOf']}；指定候选{result['candidateCount']}项。满足条件{len(result['selected'])}项，不满足{len(result['excluded'])}项，资料不足{len(result['unknown'])}项。",'满足条件仅表示符合本次研究阈值，不表示值得持有或未来表现更好。','','## 条件与实际覆盖','| 研究条件 | 可判定对象 | 输入对象 |','| --- | ---: | ---: |']
    for item in result['coverage']:lines.append('| '+safe(describe(item['condition']))+' | '+str(item['usable'])+' | '+str(item['total'])+' |')
    lines+=['','覆盖数只针对本次条件，不代表七个维度全部齐备，也不是结论置信度。','', '## 逐项结果','| 名称 | 代码 | 市场 | 结果 |','| --- | --- | --- | --- |']
    for group,label in [('selected','满足条件'),('excluded','不满足条件'),('unknown','资料不足')]:
        for row in result[group]:lines.append('| '+' | '.join(safe(x) for x in [row.get('name') or row['code'],row['code'],row['market'],label])+' |')
    lines+=['','## 指标与条件逐项对照','下列数值来自本次可判定的证据；证据不可核验或口径不匹配时不展示为有效指标。','| 代码 | 条件 | 实际指标 | 判定 |','| --- | --- | ---: | --- |']
    candidates={(r['kind'],r['market'],r['code']):r for r in spec['candidates']}
    for group in ['selected','excluded','unknown']:
        for row in result[group]:
            candidate=candidates[(row['kind'],row['market'],row['code'])]
            for check in row['checks']:
                rule=check['condition']
                if rule['kind']!='metric':continue
                value='资料不足'
                if check['passed'] is not None:
                    ev=candidate['fields'][rule['field']];value=display(ev['value'],ev.get('unit'))
                label='满足' if check['passed'] is True else '不满足' if check['passed'] is False else '不可判定'
                lines.append('| '+' | '.join(safe(x) for x in [row['code'],describe(rule),value,label])+' |')
    lines+=['','## 缺口与条件差异']
    for row in result['excluded']+result['unknown']:
        for check in row['checks']:
            if check['passed'] is not True:lines.append('- '+row['code']+'：'+safe(describe(check['condition']))+'；'+check['reason'])
    for gap in result.get('rankingGaps',[]):lines.append('- '+gap['code']+'：'+gap['reason'])
    lines+=['','## 可比排序组']
    if not result['rankingGroups']:lines.append('没有可展示的排序组；未设置排序或可用排序数据不足。')
    for index,group in enumerate(result['rankingGroups'],1):
        date,basis,window,unit,tracking=group['comparisonBasis']
        lines += ['',f"第{index}组：资料日期{date}；区间{window or '未指定'}；单位{unit or '未指定'}。不同组不直接比较排名。",'口径标识：'+safe(basis),'| 品种 | 市场 | 代码 | 排序字段值 | 来源 |','| --- | --- | --- | ---: | --- |']
        for row in group['rows']:lines.append('| '+' | '.join(safe(x) for x in [row['kind'],row['market'],row['code'],row['value'],'[排序数据来源]('+row['sourceUrl']+')'])+' |')
    lines += ['', '## 本次使用的资料来源']
    for row in spec['candidates']:
        used=[]
        for rule in result['conditions']:
            ev=row.get('fields',{}).get(rule['field']) if rule['kind']=='metric' else row.get('tags',{}).get(rule['dimension']) if rule['kind']=='tag' else row.get('holdings')
            if ev and ev.get('sourceUrl'):
                for url in links(ev):used.append((url,ev.get('observedAt','未注明'),ev.get('basis','未注明')))
        rank=spec.get('rank')
        if rank:
            ev=row.get('fields',{}).get(rank['field'])
            if ev and ev.get('sourceUrl'):
                for url in links(ev):used.append((url,ev.get('observedAt','未注明'),ev.get('basis','未注明')))
        for url,date,basis in dict.fromkeys(used):lines += ['- '+row['code']+'，资料日期'+date+'，口径：'+safe(basis),url]
    lines+=['','## 研究边界']+['- '+x for x in result['limitations']]+['',result['riskNotice']]
    return '\n'.join(lines)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if any(x.exists() for x in [a.out,a.out.with_suffix('.md'),a.out.with_suffix('.html')]):raise FileExistsError('输出已存在')
    spec=json.loads(a.input.read_text(encoding='utf-8-sig'));r=screen(spec)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open('x',encoding='utf8') as f:json.dump(r,f,ensure_ascii=False,indent=2,allow_nan=False)

    text=markdown(r,spec);a.out.with_suffix('.md').write_text(text,encoding='utf-8');a.out.with_suffix('.html').write_text(render_html(text,title='多维条件研究'),encoding='utf-8')
