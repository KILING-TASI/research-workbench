"""One-level verified feeder stock exposure; leave every other asset unexpanded."""
import argparse,json,hashlib
from decimal import Decimal
from pathlib import Path
from verify_original import compact
from target_fund_link import attach_child
from research_brief_html import render
from collection_validation import unique_pairs,reject_constant,finite_json_float
from disclosed_rate_scenario import numeric

def build(dossier):
 if not isinstance(dossier,dict) or any(not isinstance(dossier.get(k),dict) for k in ['report','targetReport','targetFundLink','fundInvestmentAccounting']):raise ValueError('联接基金穿透须含父子报告与关系核对对象')
 parent=dossier['report'];child=dossier['targetReport'];link=dossier['targetFundLink'];accounting=dossier['fundInvestmentAccounting']
 for report in [parent,child]:
  h=report.get('holdings')
  if not isinstance(h,dict) or not isinstance(h.get('holdings'),list):raise ValueError('股票快照须为金额及明细对象')
  metadata=report.get('metadata')
  if not isinstance(metadata,dict) or any(h.get(k)!=v for k,v in {'id':report.get('code'),'reportDate':report.get('reportDate'),'publishedAt':metadata.get('publishedAt'),'sourceUrl':metadata.get('sourceUrl')}.items()):raise ValueError('父子股票快照与报告身份或日期不一致')
  for row in h['holdings']:
   if not isinstance(row,dict) or any(not isinstance(row.get(k),str) or not row[k].strip() for k in ['securityNamespace','code','name','locator']):raise ValueError('股票明细缺身份、名称或原文定位')
   if 'shareClass' in row and (not isinstance(row['shareClass'],str) or not row['shareClass'].strip()):raise ValueError('证券份额类别须为文字')
   if numeric(row.get('marketValueCNY'))<0:raise ValueError('股票金额无效')
 if not isinstance(accounting.get('rows'),list) or any(not isinstance(row,dict) or not isinstance(row.get('name'),str) or not row['name'].strip() for row in accounting['rows']):raise ValueError('基金投资明细须为含全名的对象数组')
 attach_child(link,child)
 if link['reportDate']!=parent['reportDate'] or link['asOf']!=parent['asOf']:raise ValueError('父报告与目标关系时点不一致')
 if parent.get('status')!='副本身份及股票持仓勾稽完成':raise ValueError('父基金直接股票未完成勾稽')
 if hashlib.sha256(Path(parent['documentPath']).read_bytes()).hexdigest()!=parent['sha256']:raise ValueError('父报告哈希变化')
 if accounting.get('sourceSha256')!=parent['sha256'] or link['sourceSha256']!=parent['sha256']:raise ValueError('基金投资、目标关系与父报告来源不一致')
 if accounting.get('reportDate')!=parent['reportDate'] or accounting.get('asOf')!=parent['asOf']:raise ValueError('会计核对时点不一致')
 if accounting.get('accountingTotalVerified') is not True:raise ValueError('基金投资会计总额未核对')
 matches=[x for x in accounting['rows'] if compact(x['name'])==compact(link['target']['name'])]
 if len(matches)!=1:raise ValueError('目标全名未唯一匹配基金投资行，不按简称猜测')
 parent_nav=numeric(parent['holdings']['netAssetsCNY']);child_nav=numeric(child['holdings']['netAssetsCNY'])
 if parent_nav<=0 or child_nav<=0 or numeric(accounting['netAssetsCNY'])!=parent_nav:raise ValueError('净资产分母不一致')
 amount=numeric(matches[0]['marketValueCNY']);target_weight=amount/parent_nav
 if not Decimal(0)<=target_weight<=Decimal(1):raise ValueError('不支持杠杆或异常目标权重')
 merged={};direct=Decimal(0);indirect=Decimal(0)
 for label,report,scale in [('直接股票',parent,Decimal(1)),('目标ETF底层股票',child,target_weight)]:
  h=report['holdings'];nav=Decimal(str(h['netAssetsCNY']))
  keys=[(x['securityNamespace'],x['code'],x.get('shareClass','ordinary')) for x in h['holdings']]
  if len(set(keys))!=len(keys):raise ValueError('同一报告股票明细重复，不能重复穿透')
  if h.get('sourceSha256')!=report['sha256']:raise ValueError('股票表与报告摘要不一致')
  values=[numeric(x['marketValueCNY']) for x in h['holdings']]
  if sum(values,Decimal(0))!=numeric(h['equityMarketValueCNY']):raise ValueError('股票金额合计不一致')
  for x,v in zip(h['holdings'],values):
   if not v.is_finite() or v<0:raise ValueError('股票金额无效')
   weight=v/nav*scale;key=(x['securityNamespace'],x['code'],x.get('shareClass','ordinary'))
   row=merged.setdefault(key,dict(code=x['code'],namespace=x['securityNamespace'],shareClass=key[2],names=[],parts=[]))
   if x['name'] not in row['names']:row['names'].append(x['name'])
   row['parts'].append(dict(route=label,fundCode=report['code'],weight=str(weight),locator=x.get('locator'),sourceSha256=report['sha256'],sourceUrl=report['metadata']['sourceUrl']))
   if label=='直接股票':direct+=weight
   else:indirect+=weight
 total=direct+indirect
 if total>1:raise ValueError('股票敞口超过净资产，不支持此杠杆情形')
 for row in merged.values():row['weight']=str(sum((Decimal(x['weight']) for x in row['parts']),Decimal(0)))
 rows=sorted(merged.values(),key=lambda x:Decimal(x['weight']),reverse=True)
 return dict(type='verified-one-level-feeder-equity',code=parent['code'],targetCode=child['code'],reportDate=parent['reportDate'],asOf=parent['asOf'],targetInvestmentWeight=str(target_weight),directEquityWeight=str(direct),targetUnderlyingEquityWeight=str(indirect),knownEquityWeight=str(total),unexpandedNAVResidual=str(1-total),rows=rows,completeAssetPortfolio=False,limitations=['仅同报告期末静态一层穿透，不还原真实交易或当前持仓','未展开部分可能包含现金、其他基金、衍生品等，不等于现金或零风险','期货名义敞口不受净资产剩余比例约束，本结果不是全组合风险暴露','目标及父基金报告副本核验不等同发行人网页核验'])

def markdown(r):
 lines=['# 联接基金股票穿透','',r['code']+' → '+r['targetCode']+'；报告期'+r['reportDate']+'。',f"直接股票占净资产{Decimal(r['directEquityWeight'])*100:.2f}%，目标ETF底层股票折合{Decimal(r['targetUnderlyingEquityWeight'])*100:.2f}%，合计{Decimal(r['knownEquityWeight'])*100:.2f}%。",'重叠股票已合并；这是已核验股票部分，不是全组合风险敞口。','','| 股票 | 代码 | 占父基金净资产 | 来源路径 |','| --- | --- | ---: | --- |']
 for x in r['rows'][:20]:lines.append('| '+'／'.join(x['names'])+' | '+x['code']+' | '+f"{Decimal(x['weight'])*100:.4f}%"+' | '+'、'.join(p['route'] for p in x['parts'])+' |')
 lines+=['','完整明细及逐项原文位置保存在结果文件。']+['- '+x for x in r['limitations']]
 return '\n'.join(lines)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('dossier');p.add_argument('--out',required=True);a=p.parse_args();out=Path(a.out)
 if any(x.exists() for x in [out,out.with_suffix('.md'),out.with_suffix('.html')]):raise FileExistsError('输出已存在')
 pth=Path(a.dossier).resolve();spec=json.loads(pth.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)
 for key in ['report','targetReport']:
  report=spec.get(key)
  if isinstance(report,dict) and isinstance(report.get('documentPath'),str):
   path=Path(report['documentPath']);report['documentPath']=str(path if path.is_absolute() else pth.parent/path)
 r=build(spec);text=markdown(r);markup=render(text);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');out.with_suffix('.md').write_text(text,encoding='utf-8');out.with_suffix('.html').write_text(markup,encoding='utf-8')
