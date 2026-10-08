"""Bind selected report statements to PDF text; no semantic certification."""
import argparse, hashlib, json, re
from datetime import date
from pathlib import Path
import pdfplumber
from collection_validation import day,unique_pairs,reject_constant,finite_json_float
from research_library import url as source_url


def bind(spec, pages, document_hash):
    if spec.get('sha256') != document_hash:
        raise ValueError('原文版本不一致')
    kind=spec.get('reportType')
    if kind not in ('annual','interim','quarterly'):
        raise ValueError('报告类型须明确')
    if spec.get('purpose') not in ('report-statements','manager-annual-views'):
        raise ValueError('用途未明确')
    if spec['purpose']=='manager-annual-views' and kind!='annual':
        raise ValueError('经理观点入口仅接受年报；中报季报用报告陈述入口')
    source_url(spec.get('sourceUrl'))
    if not day(spec['periodEnd'])<=day(spec['publishedAt'])<=day(spec['asOf']):
        raise ValueError('披露期或截止日不一致')
    if spec.get('provenance') not in ('official-original','third-party-report-copy'):
        raise ValueError('须标明原文或副本来源')
    rows=spec.get('statements')
    if not isinstance(rows,list) or not rows:
        raise ValueError('需选定陈述')
    seen=set();result=[]
    for r in rows:
        if not isinstance(r,dict):raise ValueError('陈述须为对象')
        cid=r.get('id');page=r.get('page');quote=r.get('quote')
        if not isinstance(cid,str) or not cid.strip() or cid in seen:
            raise ValueError('陈述编号重复或为空')
        seen.add(cid)
        if not isinstance(page,int) or isinstance(page,bool) or page not in pages:
            raise ValueError('PDF物理页不存在')
        if not isinstance(quote,str) or not quote.strip() or re.sub(r'\s+','',quote) not in re.sub(r'\s+','',pages[page]):
            raise ValueError('陈述摘录未匹配原文')
        if r.get('category') not in ('reported-performance','retrospective-explanation','forward-looking-view'):
            raise ValueError('须区分披露表现、事后解释与展望')
        result.append(dict(r,textMatch=True,semanticSupportCertified=False,independentFactVerified=False))
    return dict(type='selected-report-statements',reportType=kind,purpose=spec['purpose'],
                periodEnd=spec['periodEnd'],publishedAt=spec['publishedAt'],asOf=spec['asOf'],
                sourceSha256=document_hash,sourceUrl=spec['sourceUrl'],provenance=spec['provenance'],
                statements=result,limitations=['文本匹配不证明经理解释的因果关系或所引行业数据真实',
                '展望为披露当时观点，不证明此后实际执行或未来表现','报告副本匹配不等于官方发布版本认证'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('--out',required=True);a=p.parse_args()
    input_path=Path(a.input).resolve();raw=input_path.read_bytes();s=json.loads(raw.decode('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float);doc=Path(s['documentPath'])
    if not doc.is_absolute():doc=input_path.parent/doc
    digest=hashlib.sha256(doc.read_bytes()).hexdigest()
    with pdfplumber.open(doc) as pdf:
        pages={i+1:page.extract_text() or '' for i,page in enumerate(pdf.pages)}
    r=bind(s,pages,digest);r['inputSha256']=hashlib.sha256(raw).hexdigest()
    with Path(a.out).open('x',encoding='utf8') as f:json.dump(r,f,ensure_ascii=False,indent=2)
