"""Evidence-bound product, tenure and non-performance evaluation; no product rating."""
import argparse,json,math,statistics
from pathlib import Path
from datetime import date
from fund_series_tools import day,num,source,NOTICE,annualized_pct

def evidence(r,asof):
    if not isinstance(r,dict):raise ValueError('资料证据须为对象')
    source(r['sourceUrl']);day(r['publishedAt'])
    if r['publishedAt']>asof or not isinstance(r.get('locator'),str) or not r['locator'].strip():raise ValueError('资料日期或定位缺失')

def evaluate(s):
    if not isinstance(s,dict) or not isinstance(s.get('code'),str) or not s['code'].strip():raise ValueError('基金评价须为具有代码的对象')
    for key in ('reports','history','managers'):
        if not isinstance(s.get(key,[]),list) or any(not isinstance(row,dict) for row in s.get(key,[])):raise ValueError(key+'须为对象列表')
    if not isinstance(s.get('product',{}),dict) or not isinstance(s.get('supportingResults',{}),dict):raise ValueError('产品条款及支持结果须为对象')
    code=s['code'];asof=day(s['asOf']);gaps=[];profile=[]
    labels={'objective':'投资目标','scope':'投资范围','benchmark':'业绩比较基准','restrictions':'主要限制','fees':'收费规则'}
    for field,label in labels.items():
        r=s.get('product',{}).get(field)
        if not r:gaps.append(label+'原文尚未取得');continue
        evidence(r,asof)
        if not isinstance(r.get('text'),str) or not r['text'].strip():raise ValueError('产品字段缺文本')
        profile.append({'field':field,'label':label,**r})
    structural=[];previous=None
    for r in s.get('reports',[]):
        evidence(r,asof);day(r['reportDate'])
        if r['reportDate']>r['publishedAt'] or previous and r['reportDate']<=previous['reportDate']:raise ValueError('报告期须递增且不晚于披露日')
        nav=r.get('netAssetsCNY');holders=r.get('holderCount');institution=r.get('institutionPct')
        if nav is not None:num(nav,True)
        if holders is not None:
            if isinstance(holders,bool) or not isinstance(holders,int) or holders<0:raise ValueError('持有人户数无效')
        if institution is not None:
            if not 0<=num(institution)<=100:raise ValueError('机构占比无效')
        same=previous and previous.get('scope')==r.get('scope') and bool(r.get('scope'))
        change=(nav/previous['netAssetsCNY']-1)*100 if same and nav is not None and previous.get('netAssetsCNY') else None
        if change is not None:num(change)
        structural.append({**r,'netAssetsChangePct':change,'changeMeaning':'净值变化与申赎共同影响，不能直接认定净赎回',
                           'thresholdSignals':(['披露日净资产低于研究观察阈值5000万元'] if nav is not None and nav<50_000_000 else [])+
                                              (['披露日持有人不足200户'] if holders is not None and holders<200 else [])})
        previous=r
    if not structural:gaps.append('规模与持有人结构尚未取得')
    periods=[];hs=s.get('history',[]);last=''
    for h in hs:
        day(h['date']);num(h['value'],True)
        if h['date']<=last or h['date']>asof:raise ValueError('历史重复、乱序或超过截止日')
        last=h['date']
    if hs:
        source(s['historySourceUrl'])
        if s.get('historyBasis')!='total-return':raise ValueError('任职分析需总收益序列')
    managers=s.get('managers',[]);seen=set()
    for m in managers:
        evidence(m,asof);day(m['start']);day(m['confirmedThrough'])
        if not isinstance(m.get('name'),str) or not m['name'].strip() or m['name'] in seen:raise ValueError('经理名称须非空唯一；分段任职请分别组织任务')
        seen.add(m['name']);end=day(m['end']) if m.get('end') else m['confirmedThrough']
        if m['start']>end or end>m['confirmedThrough'] or m['confirmedThrough']>m['publishedAt']:raise ValueError('任职期间与确认日期冲突')
        rows=[h for h in hs if m['start']<=h['date']<=end]
        overlaps=[{'name':other['name'],'start':max(m['start'],other['start']),'end':min(end,other.get('end') or other['confirmedThrough']),'sourceUrl':other['sourceUrl'],'publishedAt':other['publishedAt'],'locator':other['locator']}
                  for other in managers if other['name']!=m['name'] and max(m['start'],other['start'])<=min(end,other.get('end') or other['confirmedThrough'])]
        result={'name':m['name'],'reportedStart':m['start'],'reportedEnd':m.get('end'),'confirmedThrough':m['confirmedThrough'],
                'sourceUrl':m['sourceUrl'],'locator':m['locator'],'coManagementIntervals':overlaps,'observations':len(rows)}
        if len(rows)<2:result.update(status='任职区间历史不足',metrics=None)
        else:
            values=[h['value'] for h in rows];wealth=num(values[-1]/values[0],True);years=(date.fromisoformat(rows[-1]['date'])-date.fromisoformat(rows[0]['date'])).days/365.25;peak=values[0];dd=0
            for v in values:peak=max(peak,v);dd=max(dd,1-v/peak)
            result.update(status='任职与已取得历史的交集',actualStart=rows[0]['date'],actualEnd=rows[-1]['date'],
                          fullTenureCovered=rows[0]['date']==m['start'] and rows[-1]['date']==end,
                          metrics={'totalReturnPct':num((wealth-1)*100),'annualizedReturnPct':annualized_pct(wealth,years),'maximumDrawdownPct':dd*100})
            if result['metrics']['annualizedReturnPct'] is None:result['annualizedReturnUnavailableReason']='年化计算超过有限数值范围；累计收益与观察回撤按已取得区间保留，不补造年化值'
        periods.append(result)
    if not periods:gaps.append('已核验经理任职记录尚未取得')
    required={'multiPeriodHoldings':'连续多期完整持仓','contractBenchmarkComparison':'有效合同基准及同区间对标','peerComparison':'同风格可比基金池','industryAttribution':'期初行业权重、行业收益与匹配基准','liquidityStress':'底层流动性与变现假设'}
    # Dependencies must be supplied as actual result objects with dates, subjects and source evidence, not boolean completion flags.
    supplied=s.get('supportingResults',{})
    for key,label in required.items():
        item=supplied.get(key)
        if not item:gaps.append(label+'仍需补充')
        elif not isinstance(item,dict) or item.get('code')!=code or item.get('asOf')!=asof or not item.get('sources') or not item.get('result'):raise ValueError('支持项须绑定同主体、同截止日的实际结果及来源')
    return {'type':'fund-evaluation-foundation','code':code,'asOf':asof,'profile':profile,'structure':structural,'managerPeriods':periods,
            'missing':gaps,'sources':list(dict.fromkeys([r['sourceUrl'] for r in profile+structural+periods]+([s['historySourceUrl']] if hs else []))),
            'riskNotice':NOTICE,'limitations':['产品条款摘录须阅读上下文，年报产品说明不能代替有效合同全文',
                            '任职指标只属于产品在该区间的表现，共同管理期不分配给某个人，不跨产品加总重复收益',
                            '开放结束任职只计算到原文确认日期，不自动延长到今天；历史不全时显示实际交集',
                            '5000万元/200户仅观察线索；定期报告不能证明连续60个工作日触发，不作清盘判断',
                            '机构占比和户数通常为定期披露快照；不声称实时筹码结构或赎回预测',
                            '基础评价补充不等于完整尽调，不输出统一优劣分数或买卖建议']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    r=evaluate(json.loads(a.input.read_text(encoding='utf-8-sig')));a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open('x',encoding='utf8') as f:json.dump(r,f,ensure_ascii=False,indent=2,allow_nan=False)
