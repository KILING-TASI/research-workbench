"""Name-based candidate discovery; no investment exposure inference."""
import argparse,datetime as dt,hashlib,json,re,urllib.request
from pathlib import Path
from collection_validation import unique_pairs,reject_constant,finite_json_float
URL='https://fund.eastmoney.com/js/fundcode_search.js'
def parse(raw):
 m=re.fullmatch(r"\s*var\s+r\s*=\s*(\[.*\])\s*;?\s*",raw,re.S)
 if not m:raise ValueError('基金目录格式不匹配')
 rows=json.loads(m.group(1),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float);seen=set();result=[]
 for row in rows:
  if not isinstance(row,list) or len(row)<4 or not isinstance(row[0],str) or not re.fullmatch(r'\d{6}',row[0]) or any(not isinstance(row[k],str) or not row[k].strip() for k in [2,3]):raise ValueError('目录行格式不匹配')
  if row[0] in seen:raise ValueError('目录代码重复')
  seen.add(row[0]);result.append(dict(code=row[0],name=row[2],fundType=row[3]))
 return result
def discover(rows,terms,exclude=None,fund_type=None,mode='any',limit=100):
 if mode not in ('any','all'):raise ValueError('匹配方式须any或all')
 if not isinstance(terms,list) or not terms or any(not isinstance(t,str) or not t.strip() for t in terms):raise ValueError('关键词须为非空文字列表')
 if exclude is not None and (not isinstance(exclude,list) or any(not isinstance(t,str) or not t.strip() for t in exclude)):raise ValueError('排除词须为非空文字列表')
 if fund_type is not None and (not isinstance(fund_type,str) or not fund_type.strip()):raise ValueError('基金类型须为非空文字')
 if not isinstance(limit,int) or isinstance(limit,bool) or not 1<=limit<=5000:raise ValueError('limit须1至5000')
 selected=[]
 for r in rows:
  matched=[t for t in terms if t.casefold() in r['name'].casefold()]
  if not matched or (mode=='all' and len(matched)!=len(terms)):continue
  if any(t.casefold() in r['name'].casefold() for t in (exclude or [])):continue
  if fund_type and fund_type not in r['fundType']:continue
  selected.append(dict(r,matchedTerms=matched,themeVerification='仅名称匹配，投资主题未核验'))
 selected.sort(key=lambda r:r['code'])
 return dict(matchedCount=len(selected),truncated=len(selected)>limit,candidates=selected[:limit],codes=[r['code'] for r in selected[:limit]])
def main():
 a=argparse.ArgumentParser();a.add_argument('--term',action='append',required=True);a.add_argument('--exclude',action='append');a.add_argument('--fund-type');a.add_argument('--mode',default='any');a.add_argument('--limit',type=int,default=100);a.add_argument('--raw');a.add_argument('--out',required=True);v=a.parse_args()
 out=Path(v.out)
 if out.exists() or out.with_suffix('.md').exists():raise FileExistsError('输出已存在')
 if v.raw:raw=Path(v.raw).read_text(encoding='utf-8-sig');retrieved=None
 else:
  with urllib.request.urlopen(urllib.request.Request(URL,headers={'User-Agent':'Mozilla/5.0'}),timeout=20) as response:raw=response.read().decode('utf-8-sig')
  retrieved=dt.datetime.now(dt.timezone.utc).isoformat()
 rows=parse(raw);result=discover(rows,v.term,v.exclude,v.fund_type,v.mode,v.limit)
 result.update(sourceUrl=URL,retrievedAt=retrieved,processedAt=dt.datetime.now(dt.timezone.utc).isoformat(),catalogCount=len(rows),sha256=hashlib.sha256(raw.encode()).hexdigest(),limitations=['名称匹配不证明真实持仓主题；需核对合同与报告','目录包括不同份额和后端收费代码，未合并为同一产品','基金目录中的ETF联接不是场内ETF；不据名称建立交易身份','未取得收益、规模、评级等数据；可将代码交给批量研究入口','当前目录不是历史时点冻结目录'])
 out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 lines=['# 基金名称候选检索','',f"目录包含 {len(rows)} 个代码，名称匹配 {result['matchedCount']} 项，展示 {len(result['candidates'])} 项。",'', '以下仅为名称线索，尚未核实投资主题、持仓或场内交易身份。','', '| 代码 | 名称 | 供应商类型 | 匹配词 |','| --- | --- | --- | --- |']
 for r in result['candidates']:lines.append('| '+' | '.join([r['code'],r['name'].replace('|','/'),r['fundType'],','.join(r['matchedTerms'])])+' |')
 lines+=['',f'来源：{URL}','']+result['limitations'];out.with_suffix('.md').write_text('\n'.join(lines),encoding='utf-8')
if __name__=='__main__':main()
