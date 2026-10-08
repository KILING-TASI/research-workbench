"""Request-triggered fund detail batch; failures and original responses retained."""
import argparse,datetime as dt,json,re
from pathlib import Path
from fund_details import extract,markdown,attach_manager_report,attach_holdings_report
from portable_collect import get
from fund_series_tools import day
from collection_validation import unique_pairs,reject_constant

def run(spec,out):
 if not isinstance(spec,dict):raise ValueError('批量基金请求须为对象')
 day(spec.get('asOf'));requests=spec.get('requests')
 if not isinstance(requests,list) or not 1<=len(requests)<=50:raise ValueError('需1至50只指定基金')
 codes=[]
 for item in requests:
  if not isinstance(item,dict) or not isinstance(item.get('code'),str) or not re.fullmatch(r'\d{6}',item['code']):raise ValueError('基金代码须六位字符串')
  codes.append(item['code'])
 if len(set(codes))!=len(codes):raise ValueError('基金代码重复')
 out=Path(out)
 if out.exists():raise FileExistsError('输出目录已存在')
 out.mkdir(parents=True);rows=[]
 for item in requests:
  code=item['code'];folder=out/code;folder.mkdir();row=dict(code=code,status='failed',sourceUrl='https://fund.eastmoney.com/pingzhongdata/'+code+'.js')
  try:
   offline=bool(item.get('raw'));raw=Path(item['raw']).read_bytes() if offline else None;text=raw.decode('utf-8-sig') if offline else get(row['sourceUrl'])
   if offline:(folder/'provider.js').write_bytes(raw)
   else:(folder/'provider.js').write_text(text,encoding='utf8')
   retrieved=None if offline else dt.datetime.now(dt.timezone.utc).isoformat()
   r=extract(text,code,spec['asOf'],retrieved)
   for key,fn in [('managerReport',attach_manager_report),('holdingsReport',attach_holdings_report)]:
    if item.get(key):fn(r,json.loads(Path(item[key]).read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant))
   report_text=markdown(r)
   (folder/'result.json').write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
   (folder/'研究明细.md').write_text(report_text,encoding='utf8')
   row.update(status='available',name=r['name'],retrievedAt=retrieved,inputMode='saved-provider-response' if offline else 'live-provider-request',resultPath=str(folder/'result.json'),gaps=r['gaps'])
  except Exception as exc:
   row.update(reason=str(exc),rawRetained=(folder/'provider.js').exists())
  rows.append(row)
 result=dict(asOf=spec['asOf'],requestedCount=len(rows),availableCount=sum(x['status']=='available' for x in rows),failedCount=sum(x['status']=='failed' for x in rows),rows=rows,limitations=['指定基金池，不是全市场扫描','逐基金阶段区间可能不同；本结果不是共同区间横向排名','关联证据失败时该基金不标为完成；原始渠道响应仍保留','离线响应的原获取时间未知；不冒充本次新取数'])
 (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
 lines=['# 基金池明细研究','',f"请求{result['requestedCount']}只，取得明细{result['availableCount']}只，失败{result['failedCount']}只。取得明细不等于完整研究或原文核验完成；失败不表示基金不存在或不符合筛选条件。",'', '|基金|结果|说明|','|---|---|---|']
 for row in rows:lines.append('|'+row['code']+' '+row.get('name','')+'|'+row['status']+'|'+row.get('reason','已生成单基金明细；尚需核验项目见各基金报告').replace('|','／').replace('\n',' ')+'|')
 lines+=['',*result['limitations']];(out/'批量研究说明.md').write_text('\n'.join(lines),encoding='utf8')
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out-dir',type=Path,required=True);a=p.parse_args();run(json.loads(a.input.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant),a.out_dir)
