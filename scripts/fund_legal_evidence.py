"""Bind historical fee-amendment evidence to an identified fund dossier."""
import argparse,json,hashlib
from pathlib import Path
from fund_document_archive import normalize
from fund_fee_amendment import run as amendment,markdown as amendment_text
from research_brief_html import render
from collection_validation import day,unique_pairs,reject_constant

def build(s):
 if not isinstance(s,dict) or any(not isinstance(s.get(k),dict) for k in ['dossier','amendmentArchive']) or not isinstance(s['dossier'].get('report'),dict):raise ValueError('法律文件关联须含基金档案、报告及调整归档对象')
 if not isinstance(s.get('fundFullName'),str) or not s['fundFullName'].strip():raise ValueError('须明确基金全名')
 d=s['dossier'];r=d['report'];a=s['amendmentArchive'];name=s['fundFullName']
 day(d.get('asOf'))
 if d['code']!=r['code'] or d['asOf']!=r['asOf'] or d['asOf']!=a['asOf']:raise ValueError('基金档案身份或截止日不一致')
 if r.get('identityStatus')!='matched' or normalize(name) not in normalize(r['metadata']['title']):raise ValueError('基金全名未在已核验报告标题匹配')
 if hashlib.sha256(Path(r['documentPath']).read_bytes()).hexdigest()!=r['sha256']:raise ValueError('基金报告摘要不一致')
 ev=amendment(a,name)
 return dict(type='fund-legal-evidence-supplement',code=d['code'],asOf=d['asOf'],fundFullName=name,reportIdentityEvidence=dict(sourceUrl=r['metadata']['sourceUrl'],sourceSha256=r['sha256'],reportDate=r['reportDate']),historicalFeeAmendment=ev,currentEffectiveFees=None,status='历史调整证据已关联；当前有效费率未完成核验',limitations=['全名在基金报告和调整名单分别精确匹配；不扩展为全部份额收费规则','未取得之后全部修订，不据此覆盖渠道费率或认定当前收费','原始研究档案保留不变；本结果为独立证据补充'])

def markdown(r):
 return '# 基金法律文件证据补充\n\n基金'+r['code']+'；截止日'+r['asOf']+'。\n\n'+r['status']+'。\n\n[基金身份报告]('+r['reportIdentityEvidence']['sourceUrl']+')\n\n'+amendment_text(r['historicalFeeAmendment']).replace('# ','## ',1)+'\n\n'+ '\n'.join('- '+x for x in r['limitations'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if any(x.exists() for x in [a.out,a.out.with_suffix('.md'),a.out.with_suffix('.html')]):raise FileExistsError('输出已存在')
 r=build(json.loads(a.input.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant));t=markdown(r);markup=render(t);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');a.out.with_suffix('.md').write_text(t,encoding='utf-8');a.out.with_suffix('.html').write_text(markup,encoding='utf-8')
