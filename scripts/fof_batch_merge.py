"""Merge explicitly selected FOF batches without overwriting earlier success."""
import argparse,hashlib,json
from pathlib import Path
from collection_validation import day,unique_pairs,reject_constant

def merge(parent,batches):
 if not isinstance(parent,dict) or not isinstance(parent.get('holdings'),list) or not parent['holdings'] or any(not isinstance(h,dict) or not isinstance(h.get('code'),str) or not h['code'].strip() for h in parent['holdings']):raise ValueError('父持仓须为含代码的对象数组')
 day(parent.get('reportDate'))
 if not isinstance(batches,list) or not batches or any(not isinstance(item,dict) or not isinstance(item.get('result'),dict) for item in batches):raise ValueError('需明确批次结果对象数组')
 holdings=parent['holdings'];codes=[h['code'] for h in holdings]
 if len(set(codes))!=len(codes):raise ValueError('父持仓代码重复')
 selected={};nodes={};asof=None
 for item in batches:
  result=item['result'];start=item['startIndex'];limit=item['limit']
  if not isinstance(result.get('rows'),list) or any(not isinstance(r,dict) for r in result['rows']) or not isinstance(result.get('nodes'),dict) or any(not isinstance(n,dict) for n in result['nodes'].values()):raise ValueError('批次行与节点结构无效')
  if day(result.get('asOf'))<day(parent['reportDate']):raise ValueError('批次截止日早于报告期')
  if type(start)!=int or type(limit)!=int or not 0<=start<len(codes) or limit<1:raise ValueError('批次范围无效')
  if result['reportDate']!=parent['reportDate']:raise ValueError('批次报告期不一致')
  if asof is None:asof=result['asOf']
  if result['asOf']!=asof:raise ValueError('批次截止日不一致')
  if [r['code'] for r in result['rows']]!=codes:raise ValueError('批次父持仓顺序或范围不同')
  if result.get('batch') and not (result['batch']['startIndex']<=start and start+limit<=result['batch']['startIndex']+result['batch']['limit']):raise ValueError('选定范围超出已执行批次')
  active=result['rows'][start:start+limit]
  expected_nodes={r['code'] for r in result['rows'] if r['status']=='parsed-equity'}
  if set(result['nodes'])!=expected_nodes:raise ValueError('已解析状态与子节点不一致')
  for i,row in enumerate(active,start):
   code=row['code']
   if code in selected:raise ValueError('选定批次重叠，须明确保留哪个版本')
   if row['reportDate']!=parent['reportDate'] or row['fofWeight']!=holdings[i]['weight']:raise ValueError('批次权重或报告期不同于父快照')
   selected[code]=dict(row)
  nodes.update({k:v for k,v in result['nodes'].items() if k in {r['code'] for r in active}})
 if asof is None:raise ValueError('至少选定一个批次')
 rows=[dict(selected[h['code']]) if h['code'] in selected else dict(code=h['code'],name=h.get('name'),reportDate=parent['reportDate'],fofWeight=h['weight'],status='not-attempted',reason='未纳入选定已执行批次') for h in holdings]
 counts=dict(requested=len(codes),attempted=len(selected),downloaded=sum(r['status'] in ('parsed-equity','downloaded-unparsed') for r in rows),parsed=len(nodes),downloadedUnparsed=sum(r['status']=='downloaded-unparsed' for r in rows),notAttempted=len(codes)-len(selected),pending=len(codes)-len(nodes))
 return dict(type='fof-selected-batch-merge',asOf=asof,reportDate=parent['reportDate'],rows=rows,nodes=nodes,pendingReports=[r for r in rows if r['status']!='parsed-equity'],counts=counts,limitations=['按明确批次范围及父快照合并，不按文件时间选新旧版本','股票解析成功不代表子基金全资产穿透，非股票仓位仍需核验','不认证原件真实性或完整覆盖；来源文件另行绑定'])

def run(spec,base):
 source=Path(base)/spec['parent'];raw=source.read_bytes();parent=json.loads(raw.decode('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant);batches=[];bindings=[dict(path=str(source.resolve()),sha256=hashlib.sha256(raw).hexdigest())]
 for item in spec['batches']:
  p=Path(base)/item['path'];raw=p.read_bytes();r=json.loads(raw.decode('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant);batches.append(dict(result=r,startIndex=item['startIndex'],limit=item['limit']));bindings.append(dict(path=str(p.resolve()),sha256=hashlib.sha256(raw).hexdigest()))
 result=merge(parent,batches);result['sourceBindings']=bindings;return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();result=run(json.loads(a.input.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant),a.input.resolve().parent)
 with a.out.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
