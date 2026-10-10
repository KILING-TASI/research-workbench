# SPDX-License-Identifier: MIT
"""Explicit disclosure worksheets. Does not fetch, infer ownership, or certify filings."""
from review_io import cli,evidence,number,day,instant

TOPICS={'earnings-forecast':'业绩预告','shareholders':'股东户数','pledge':'股权质押','unlock':'限售解禁','placement':'定向增发','inquiry':'问询函/关注函','competition':'同业竞争','incentive':'股权激励'}

def review(spec):
    if set(spec)!={'asOf','topic','entity','records'} or spec['topic'] not in TOPICS or not isinstance(spec['entity'],str) or not spec['entity'].strip():raise ValueError('需截止、专题、明确主体和记录')
    cutoff=instant(spec['asOf']);records=spec['records']
    if not isinstance(records,list) or not records or len(records)>1000:raise ValueError('记录须为1至1000条')
    seen=set();visible=[];excluded=[]
    for row in records:
        if not isinstance(row,dict) or not isinstance(row.get('id'),str) or not row['id'] or row['id'] in seen:raise ValueError('记录ID缺失或重复')
        seen.add(row['id'])
        if row.get('entity')!=spec['entity']:raise ValueError('记录主体不一致，不按名称猜同一控制关系')
        if row.get('stage') not in ('proposal','announced','implemented','cancelled','corrected','unknown'):raise ValueError('需明确阶段，不把计划当实施')
        if not evidence(row,spec['asOf']):excluded.append(row['id']);continue
        body={'id':row['id'],'source':row['source'],'locator':row['locator'],'sourceVersion':row['sourceVersion'],'rawSourceSha256':row['rawSourceSha256'],'stage':row['stage'],'facts':row.get('facts'),'originalVerified':False}
        facts=row.get('facts')
        if not isinstance(facts,dict):raise ValueError('需明确原文事实字段')
        topic=spec['topic']
        if topic=='earnings-forecast':
            needed={'periodStart','periodEnd','metric','profitAttribution','scope','currency','unit','lower','upper','previousActual'}
            if set(facts)!=needed or facts['currency']!='CNY' or facts['unit'] not in ('元','万元','亿元') or facts['profitAttribution'] not in ('parent','consolidated','unknown') or not isinstance(facts['scope'],str) or not facts['scope']:raise ValueError('预告需期间、科目、归属、范围、单位和上下限/上期实际值')
            if day(facts['periodStart'])>day(facts['periodEnd']):raise ValueError('预告期间倒置')
            lo,hi=number(facts['lower']),number(facts['upper'])
            if lo>hi:raise ValueError('预告下限大于上限')
            prior=None if facts['previousActual'] is None else number(facts['previousActual'])
            body['rangeWidth']=str(hi-lo);body['changeVsPrevious']=None if prior is None or prior==0 else [str((lo-prior)/abs(prior)),str((hi-prior)/abs(prior))]
            body['changeBasis']='(预告值-同口径上期值)/abs(上期值)；负基数不是通常同比增长率；输入声明未原文认证'
        elif topic=='shareholders':
            if set(facts)!={'observedDate','count','shareClass','scope'} or not isinstance(facts['scope'],str) or not facts['scope'] or not isinstance(facts['shareClass'],str) or not facts['shareClass']:raise ValueError('户数需观察日、份额类别和统计范围')
            count=number(facts['count'])
            if count<0 or count!=count.to_integral_value() or day(facts['observedDate'])>cutoff.date() or day(facts['observedDate'])>day(row['publishedDate']):raise ValueError('户数须非负整数且观察日不晚于披露/截止')
        else:
            if set(facts)!={'eventDate','publicStatement','denominator','implementationEvidence'}:raise ValueError('事件需明确事件日、原文陈述、分母及实施证据（未知填null）')
            if facts['eventDate'] is not None:day(facts['eventDate'])
            if not isinstance(facts['publicStatement'],str) or not facts['publicStatement'].strip():raise ValueError('需原文陈述，不从标题补正文事实')
            if row['stage']=='implemented' and not facts['implementationEvidence']:raise ValueError('标实施须有明确依据，程序不认证其真实性')
        corrected=row.get('correctsId')
        if row['stage']=='corrected' and (not isinstance(corrected,str) or corrected not in [r['id'] for r in visible]):raise ValueError('更正须指向已可见的先前记录，旧记录不删除')
        body['correctsId']=corrected;visible.append(body)
    changes=[]
    if spec['topic']=='shareholders':
        grouped={}
        for row in visible:
            f=row['facts'];grouped.setdefault((f['scope'],f['shareClass']),[]).append(row)
        for group,rows in grouped.items():
            rows=sorted(rows,key=lambda r:r['facts']['observedDate'])
            if len({r['facts']['observedDate'] for r in rows})!=len(rows):raise ValueError('同日期户数多版本需先明确更正关系；不按晚日期静默覆盖')
            for a,b in zip(rows,rows[1:]):
                old,new=number(a['facts']['count']),number(b['facts']['count'])
                changes.append({'beforeId':a['id'],'afterId':b['id'],'scope':group[0],'shareClass':group[1],'countDifference':str(new-old),'relativeDifference':None if old==0 else str((new-old)/old)})
    return {'methodVersion':'explicit-disclosure-review/1.0','conclusion':TOPICS[spec['topic']]+'按声明口径复查；标题、原文事实和实际实施分开，未知不补成结论。','topic':spec['topic'],'records':visible,'excludedAfterCutoffIds':excluded,'shareholderChanges':changes,'humanRows':[['可见记录',len(visible)],['截止后排除',len(excluded)],['同口径户数变化',len(changes)]],'limitations':['本入口复查提供的结构化底稿，不自动下载或解析任意PDF','来源/定位/摘要依赖输入，结构通过不等于原文已核','业绩预告不是实际业绩，区间不代表概率或估值','股东户数下降不证明主力买入，不识别账户；质押/解禁/定增不等于卖出','强制披露条件、主体资格与规则版本需规则库另核，未给自动违法判断']}

if __name__=='__main__':raise SystemExit(cli({'review':review},'公告专题底稿复查'))
