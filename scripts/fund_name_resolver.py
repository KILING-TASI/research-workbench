"""Resolve explicit full fund names; ambiguous names remain user choices."""
import datetime as dt
import hashlib
import json
from pathlib import Path
from theme_candidates import parse, URL
from portable_collect import get
from collection_validation import unique_pairs, reject_constant, finite_json_float
from research_brief_html import render


def resolve(names, out, online=False, reuse_from=None, fetch=get):
    if not isinstance(names,list) or not 2<=len(names)<=10 or any(not isinstance(n,str) or not n.strip() for n in names):
        raise ValueError('需要2至10个明确基金名称；没有份额名称时给候选，不猜A/C')
    names=[name.strip() for name in names]
    if len(set(names))!=len(names):raise ValueError('基金名称重复')
    out=Path(out);out.mkdir(parents=True)
    source={'sourceUrl':URL,'verification':'third-party-current-catalog','reused':False}
    raw=None
    if reuse_from:
        root=Path(reuse_from).resolve();directory=root/'identity'
        try:
            path=(directory/'catalog.txt').resolve()
            if not path.is_relative_to(root):raise ValueError('名称目录文件指向复用目录外')
            metadata=(directory/'result.json').resolve()
            if not metadata.is_relative_to(root):raise ValueError('名称目录记录指向复用目录外')
            if path.stat().st_size>16*1024*1024 or metadata.stat().st_size>4*1024*1024:raise ValueError('名称目录或记录过大')
            meta=json.loads(metadata.read_text('utf-8'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)['catalog']
            retrieved=dt.datetime.fromisoformat(meta['retrievedAt'])
            if retrieved.tzinfo is None or retrieved>dt.datetime.now(dt.timezone.utc):raise ValueError('名称目录取得时间无时区或晚于当前时间')
            candidate=path.read_text('utf-8')
            if meta['sourceUrl']!=URL or hashlib.sha256(candidate.encode()).hexdigest()!=meta['sha256']:raise ValueError('名称目录摘要或来源不匹配')
            parse(candidate)
            raw=candidate;source.update(meta,reused=True)
        except (OSError,ValueError,KeyError,TypeError) as error:source['reuseError']=str(error)
    if raw is None:
        if not online:raise ValueError('未取得可复用名称目录；请主动启用--online或改用已确认代码')
        raw=fetch(URL);source.update(retrievedAt=dt.datetime.now(dt.timezone.utc).isoformat(),sha256=hashlib.sha256(raw.encode()).hexdigest())
    (out/'catalog.txt').write_text(raw,'utf-8')
    (out/'catalog-source.json').write_text(json.dumps(source,ensure_ascii=False,indent=2),'utf-8')
    rows=parse(raw);matches=[];codes=[]
    for name in names:
        exact=[r for r in rows if r['name']==name]
        candidates=exact or [r for r in rows if name.casefold() in r['name'].casefold()]
        selected=exact[0] if len(exact)==1 and not ('ETF' in exact[0]['name'].upper() and '联接' not in exact[0]['name']) else None
        if selected:codes.append(selected['code'])
        matches.append({'query':name,'status':'exact-current-name' if selected else 'needs-confirmation',
                        'selectedCode':selected['code'] if selected else None,'candidateCount':len(candidates),
                        'truncated':len(candidates)>20,'candidates':candidates[:20]})
    ready=all(row['selectedCode'] for row in matches) and len(codes)==len(set(codes))
    result={'status':'resolved' if ready else 'needs-clarification','codes':codes if ready else [],'matches':matches,'catalog':source,
            'limitations':['当前第三方目录不是历史时点证券主数据；复用目录不证明当前名称仍未变化','内容摘要仅检查文件与记录一致，不认证第三方数据真实性','名称精确匹配不证明合同、费率、经理或投资主题','短名称即使仅一个候选也需确认；ETF本体不自动送入场外基金入口']}
    (out/'catalog.txt').write_text(raw,'utf-8');(out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
    body='# 基金名称确认\n\n'+('完整名称已匹配，后续仍需核对代码与净值身份。' if ready else '名称尚不能唯一用于本次比较，请确认完整名称和份额；没有自动选择第一项。')
    for row in matches:
        body+='\n\n## '+row['query']+'\n\n'
        for candidate in row['candidates']:body+='- '+candidate['code']+'｜'+candidate['name']+'｜'+(candidate['fundType'] or '类型未披露')+'\n'
        if not row['candidates']:body+='本次目录没有匹配，不能据此断言基金不存在。\n'
        if row['truncated']:body+='候选超过20项，当前展示并不完整。\n'
    (out/'名称确认.md').write_text(body,'utf-8');(out/'名称确认.html').write_text(render(body),'utf-8')
    return result
