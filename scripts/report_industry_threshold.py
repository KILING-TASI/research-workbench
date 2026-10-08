"""Exact report-native industry threshold; never convert industries to themes."""
import argparse,json,hashlib
from pathlib import Path
from decimal import Decimal,InvalidOperation
from fund_series_tools import day,num,NOTICE
from research_brief_html import render
from collection_validation import unique_pairs,reject_constant,finite_json_float

def amount(value,positive=False):
 if isinstance(value,bool):raise ValueError('金额不能为布尔值')
 try:v=Decimal(str(value))
 except InvalidOperation:raise ValueError('金额格式无效')
 if not v.is_finite() or v<0 or positive and v<=0:raise ValueError('金额非有限、为负或净资产不大于零')
 return v

def run(s):
 d=s['dossier'];r=d['report'];i=d['reportIndustries'];asof=day(s['asOf']);threshold=num(s['minimumWeightPctOfNAV'])
 if not 0<=threshold<=100:raise ValueError('权重阈值须0至100')
 day(r['reportDate']);day(i['publishedAt']);day(i['reportDate'])
 if r['code']!=d['code'] or i['publishedAt']!=r['metadata']['publishedAt']:raise ValueError('报告代码或披露日期不一致')
 if not r.get('identityStatus'):raise ValueError('原文身份未核验')
 if d['asOf']!=asof or r['asOf']!=asof or not r['reportDate']<=i['publishedAt']<=asof:raise ValueError('截止日或披露日不一致')
 if i['code']!=d['code'] or i['reportDate']!=r['reportDate'] or i['sourceSha256']!=r['sha256'] or i['sourceUrl']!=r['metadata']['sourceUrl']:raise ValueError('行业表与报告身份来源不一致')
 if hashlib.sha256(Path(r['documentPath']).read_bytes()).hexdigest()!=r['sha256']:raise ValueError('原文摘要不一致')
 nav=amount(i['netAssetsCNY'],positive=True)
 if any(not isinstance(i.get(k),str) or not i[k].strip() for k in ['taxonomy','taxonomyVersion']):raise ValueError('需明确行业分类体系与版本')
 if not isinstance(i.get('sectors'),list) or any(not isinstance(x,dict) for x in i['sectors']):raise ValueError('行业条目须为对象列表')
 keys=[x.get('key') for x in i['sectors']]
 if any(not isinstance(k,str) or not k.strip() for k in keys) or len(keys)!=len(set(keys)):raise ValueError('行业代码缺失或重复')
 if sum(amount(x['marketValueCNY']) for x in i['sectors'])!=amount(i['equityMarketValueCNY']):raise ValueError('行业合计不一致')
 matches=[x for x in i['sectors'] if x['key']==s['industryKey']]
 if len(matches)!=1:raise ValueError('行业代码缺失或重复，不按名称猜测')
 x=matches[0];exact_weight=amount(x['marketValueCNY'])/nav*100;weight=num(float(exact_weight))
 return dict(code=d['code'],asOf=asof,reportDate=r['reportDate'],industryKey=x['key'],industryName=x['name'],taxonomy=i['taxonomy'],taxonomyVersion=i['taxonomyVersion'],weightPctOfNAV=weight,minimumWeightPctOfNAV=threshold,passed=exact_weight>=Decimal(str(threshold)),sourceUrl=i['sourceUrl'],sourceSha256=i['sourceSha256'],components=x['components'],riskNotice=NOTICE)

def markdown(r):
 return '# 报告行业权重核对\n\n'+r['code']+'，报告日'+r['reportDate']+'。\n\n'+r['industryName']+'占净资产'+f"{r['weightPctOfNAV']:.4f}%"+'，本次阈值'+str(r['minimumWeightPctOfNAV'])+'%：'+('满足' if r['passed'] else '不满足')+'。\n\n分类口径：'+r['taxonomy']+'；'+r['taxonomyVersion']+'。行业不是主题标签；仅报告快照，不代表当前持仓。\n\n[原文来源]('+r['sourceUrl']+')\n\n'+r['riskNotice']
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if any(x.exists() for x in [a.out,a.out.with_suffix('.md'),a.out.with_suffix('.html')]):raise FileExistsError('输出已存在')
 spec=json.loads(a.input.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float);doc=Path(spec['dossier']['report']['documentPath']);spec['dossier']['report']['documentPath']=str(doc if doc.is_absolute() else a.input.resolve().parent/doc)
 r=run(spec);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');t=markdown(r);a.out.with_suffix('.md').write_text(t,encoding='utf-8');a.out.with_suffix('.html').write_text(render(t),encoding='utf-8')
