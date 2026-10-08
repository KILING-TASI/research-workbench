"""On-demand public fund legal-document candidates, not official-current verification."""
import argparse,json,re,datetime as dt,hashlib
from pathlib import Path
from urllib.parse import urlencode
from fof_reports import download
from fund_series_tools import day
from collection_validation import unique_pairs,reject_constant,finite_json_float

def checked_items(items,code):
 if not isinstance(items,list) or any(not isinstance(x,dict) for x in items):raise ValueError('目录条目须为对象数组')
 result=[];seen={}
 for x in items:
  if str(x.get('FUNDCODE'))!=code:raise ValueError('目录代码不一致')
  if any(not isinstance(x.get(k),str) or not x[k].strip() for k in ['ID','TITLE']):raise ValueError('目录编号及标题须为非空文字')
  if x['ID'] in seen:
   if x!=seen[x['ID']]:raise ValueError('同公告编号存在冲突记录')
   continue
  seen[x['ID']]=x;result.append(x)
 return result

def select(items,code,asof,kind):
 day(asof)
 if kind not in ('contract','prospectus'):raise ValueError('仅支持合同或招募说明书')
 result=[]
 for x in checked_items(items,code):
  if str(x.get('FUNDCODE'))!=code:raise ValueError('目录代码不一致')
  title=x.get('TITLE','');published=str(x.get('PUBLISHDATE',''))[:10];day(published)
  wanted=('基金合同' in title if kind=='contract' else '招募说明书' in title)
  if not wanted or re.search('摘要|提示|公告|英文|对照表|对比表|补充协议|修订说明|变更说明',title) or published>asof:continue
  result.append(dict(id=x['ID'],title=title,publishedAt=published))
 return sorted(result,key=lambda x:(x['publishedAt'],x['id']),reverse=True)

def amendment_clues(items,code,asof,after=None):
 day(asof)
 if after is not None:day(after)
 clues=[];seen=set()
 for x in checked_items(items,code):
  if str(x.get('FUNDCODE'))!=code:raise ValueError('目录代码不一致')
  published=str(x.get('PUBLISHDATE',''))[:10];day(published);title=x.get('TITLE','')
  if published>asof or after and published<after:continue
  contract=bool(re.search('基金合同|招募说明书',title) and re.search('修订|修改|更新|补充|变更',title) and '公告' in title)
  fee=bool(re.search('管理费|托管费|销售服务费|费率',title) and re.search('调整|降低|调低|变更|修改',title))
  supporting=bool(re.search('基金合同|招募说明书',title) and re.search('对照表|对比表|补充协议|修订说明|变更说明',title))
  if not contract and not fee and not supporting:continue
  if x['ID'] in seen:continue
  seen.add(x['ID']);clues.append(dict(id=x['ID'],title=title,publishedAt=published,clueTypes=(['法律文件修订线索'] if contract else [])+(['费用变动线索'] if fee else [])+(['法律条款辅助材料'] if supporting else []),effectiveDate=None,relationVerified=False))
 return sorted(clues,key=lambda x:(x['publishedAt'],x['id']),reverse=True)

def run(code,asof,kind,directory,fetch=download):
 day(asof)
 if not isinstance(code,str) or not re.fullmatch(r'\d{6}',code):raise ValueError('基金代码须六位')
 if kind not in ('contract','prospectus'):raise ValueError('仅支持合同或招募说明书')
 out=Path(directory)
 if out.exists():raise FileExistsError('输出目录已存在')
 out.mkdir(parents=True);items=[];sources=[];truncated=True;total_mode=None;reported_total=None
 for page in range(1,11):
  url='https://api.fund.eastmoney.com/f10/JJGG?'+urlencode(dict(fundcode=code,pageIndex=page,pageSize=100,type=0))
  raw=fetch(url);response=json.loads(raw,object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float);data=response.get('Data') if isinstance(response,dict) else None
  if not isinstance(data,list):raise ValueError('公告目录结构异常')
  (out/f'catalog-{page}.json').write_bytes(raw);sources.append(dict(url=url,sha256=hashlib.sha256(raw).hexdigest()))
  if 'ErrCode' in response and (type(response['ErrCode']) is not int or response['ErrCode']!=0):raise ValueError('公告目录返回错误状态')
  for field,expected in [('PageIndex',page),('PageSize',100)]:
   if field in response and (type(response[field]) is not int or response[field]!=expected):raise ValueError('公告目录页码或页容量不一致')
  has_total='TotalCount' in response
  if total_mode is None:total_mode=has_total
  elif total_mode!=has_total:raise ValueError('目录总条数声明跨页缺失')
  if has_total:
   total=response['TotalCount']
   if type(total) is not int or total<0:raise ValueError('目录总条数无效')
   if reported_total is None:reported_total=total
   elif total!=reported_total:raise ValueError('目录总条数跨页变化，需重新取得一致快照')
   expected=min(100,max(0,total-len(items)))
   if len(data)!=expected:raise ValueError('目录页条数与声明总数不一致')
  elif len(data)>100:raise ValueError('目录页条数超过请求容量')
  items+=data
  checked=checked_items(items,code)
  if len(checked)!=len(items):raise ValueError('分页目录重复公告编号，覆盖未确认')
  if has_total and len(items)==reported_total or not has_total and len(data)<100:truncated=False;break
 candidates=select(items,code,asof,kind)
 clues=amendment_clues(items,code,asof,candidates[0]['publishedAt'] if candidates else None)
 result=dict(catalogCoverage='provider-declared-count-matched' if reported_total is not None and not truncated else 'bounded-or-page-length-only',reportedTotalCount=reported_total,observedItems=len(items),amendmentClues=clues,code=code,asOf=asof,kind=kind,candidates=candidates,sources=sources,truncated=truncated,retrievedAt=dt.datetime.now(dt.timezone.utc).isoformat(),status='仅目录候选，原文身份与现行有效性待核验',latestCandidateDate=candidates[0]['publishedAt'] if candidates else None,limitations=['第三方公告目录，不证明官方网页发布或当前有效','不自动把最新目录文件当成当前基金合同；补充协议及修订公告需联动核验','截断时不证明已经找到全部或最新文件','未下载原文，不据目录计算费率或投资范围'])
 (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 lines=['# 基金法律文件目录','',code+'；截止日'+asof+'。候选文件与修订线索均未确认当前有效性。','','## 完整文件候选']
 for x in candidates:lines.append('- '+x['publishedAt']+'：'+x['title']+'；公告ID '+x['id'])
 lines+=['','## 最近候选之后的修订与费用线索']
 for x in clues:lines.append('- '+x['publishedAt']+'：'+x['title']+'；公告ID '+x['id']+'；生效日及关联关系待核验')
 if not clues:lines.append('本次目录未检出标题线索，不代表没有修订或费用变化。')
 lines+=['']+result['limitations'];(out/'文件与修订线索.md').write_text('\n'.join(lines),encoding='utf-8');return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--code',required=True);p.add_argument('--as-of',required=True);p.add_argument('--kind',choices=['contract','prospectus'],required=True);p.add_argument('--out-dir',required=True);a=p.parse_args();run(a.code,a.as_of,a.kind,a.out_dir)
