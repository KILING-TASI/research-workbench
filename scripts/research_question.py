"""Conservative question router; currently closes the announcement research workflow."""
import datetime as dt
import hashlib
import json
import re
import uuid
from pathlib import Path
from security_search import search
from event_research import run as events

def run(spec,workspace,searcher=search,event_runner=events):
    question=spec.get('question')
    if not isinstance(question,str) or not question.strip() or len(question)>3000:raise ValueError('question须为1至3000字符')
    as_of=spec.get('asOf');dt.date.fromisoformat(as_of)
    refresh=spec.get('refresh',True)
    if type(refresh) is not bool or type(spec.get('onlineSearch',False)) is not bool:raise ValueError('refresh及onlineSearch须为布尔值')
    months=spec.get('months')
    detected=re.findall(r'(?:近|最近|过去)\s*([一三13])\s*个?月',question)
    if months is None:months={'一':1,'三':3,'1':1,'3':3}.get(detected[0],1) if detected else 1
    if type(months)!=int or months not in [1,3]:raise ValueError('仅支持1或3个日历月')
    tokens=re.findall(r'(?:近|最近|过去)\s*([零一二三四五六七八九十0-9]+)\s*个?月',question)
    dates=re.findall(r'\d{4}-\d{2}-\d{2}',question)
    codes=list(dict.fromkeys(re.findall(r'(?<![0-9])[0-9]{6}(?![0-9])',question)))
    result={'type':'research-question-result','version':1,'question':question,'asOf':as_of,
        'riskNotice':'仅为客观研究，不构成投资建议；不预测涨跌或输出交易指令',
        'status':'needs-clarification','resolvedSecurity':None,'stages':[], 'facts':[], 'hypotheses':[], 'gaps':[], 'evidence':[]}
    intent='events' if re.search(r'公告|新闻|事件|变化|重要|回购|减持|诉讼',question) else None
    result['intent']=intent
    if not intent:result['status']='unsupported';result['gaps'].append('当前自动问答只接通单公司公告研究；其他模块尚未接入此路由')
    elif any(t not in ['一','三','1','3'] for t in tokens) or len(set(detected))>1 or re.search(r'\d+\s*(?:天|周|年)',question):
        result['gaps'].append('问题时间范围超出1/3个月支持范围；请明确范围，未静默替换')
    elif dates and any(d!=as_of for d in dates):result['gaps'].append('问题中的日期与asOf不同，需明确研究截止日')
    elif 'months' in spec and detected and months!={'一':1,'三':3,'1':1,'3':3}[detected[0]]:result['gaps'].append('问题窗口与months冲突')
    elif len(codes)>1:result['gaps'].append('当前入口仅支持单公司，多代码不自动选择')
    else:
        code=spec.get('code') or (codes[0] if codes else None)
        if spec.get('code') and codes and spec['code']!=codes[0]:result['gaps'].append('问题代码与指定代码冲突')
        else:
            query=code or spec.get('query')
            if not query:
                m=re.search(r'(?:分析|看看|查看|查询|研究)\s*([^，。？?\s]{2,20}?)(?=最近|近|过去|的公告|公告|的新闻|新闻|有什么|$)',question)
                query=m.group(1) if m else None
            if not query:result['gaps'].append('无法可靠识别公司，请提供代码或query')
            elif spec.get('market','CN')!='CN':result['status']='unsupported';result['gaps'].append('此自动研究链仅支持A股身份检索；港美股使用events提供资料模式')
            else:
                identity=searcher(Path(workspace),query,'stock',spec.get('onlineSearch',False),100)
                result['identitySearch']=identity
                candidates=[r for r in identity['rows'] if r['kind']=='stock' and (r['code']==code if code else r['name']==query)]
                grouped={r['code']:r for r in candidates}
                if len(grouped)!=1 or identity.get('truncated'):
                    result['gaps'].append('未取得唯一完整股票身份候选；保留检索候选，不猜测代码')
                else:
                    security=next(iter(grouped.values()));result['resolvedSecurity']=security
                    result['stages'].append({'stage':'identity','status':'candidate-resolved','verification':security['identityVerification']})
                    event_spec={'market':'CN','code':security['code'],'asOf':as_of,'months':months,'refresh':refresh}
                    if 'items' in spec:event_spec['items']=spec['items']
                    timeline=event_runner(event_spec,Path(workspace));result['eventResult']=timeline
                    result['stages'].append({'stage':'events','status':timeline['collectionStatus']})
                    result['status']='partial' if timeline['timeline'] else 'data-unavailable'
                    result['facts']=[{'publishedAt':r['publishedAt'],'title':r['title'],'sourceUrl':r['sourceUrl'],'verification':'metadata-not-original-verified'} for r in timeline['timeline']]
                    result['hypotheses']=[{'eventId':r['id'],'impactPaths':r['impactPaths'],'priority':r['priority'],'judgment':'研究线索，未证实实质影响'} for r in timeline['timeline']]
                    result['evidence']=[{'sourceUrl':u,'retrievedAt':timeline['retrievedAt']} for u in timeline['sources']]
                    result['gaps']+=['尚未核验公告正文，不能判断哪些事件实质改变盈利或信用假设','财务与行情对照、估值及机构预期复盘尚未接入此链路','新闻信息流未接入；不代表全部信息已覆盖']
                    if timeline.get('error'):result['gaps'].append(timeline['error'])
    name=(result['resolvedSecurity'] or {}).get('name','未确认标的')
    if 'eventResult' in result:
        e=result['eventResult'];lines=[result['riskNotice'],f"{name}：{e['start']}至{as_of}取得{len(e['timeline'])}条公告元数据。"]
        for row in e['timeline']:lines.append(f"- {row['publishedAt']}｜{row['title']}｜{'、'.join(row['eventTypes'])}；{row['priority']}，影响待原文核查")
    else:lines=[result['riskNotice'],'当前问题尚不能直接执行研究。']
    lines+=['待补：'+'；'.join(result['gaps'])];result['answer']='\n'.join(lines)
    hashes={name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in ['research_question.py','event_research.py','security_search.py','market_collect.py']}
    result['codeHashes']=hashes;result['inputSha256']=hashlib.sha256(json.dumps(spec,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    folder=Path(workspace)/'research-data'/'question-runs'/uuid.uuid4().hex;folder.mkdir(parents=True)
    result['archivePath']=str((folder/'result.json').resolve())
    (folder/'input.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2),encoding='utf-8')
    (folder/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    (folder/'answer.md').write_text(result['answer'],encoding='utf-8')
    return result
