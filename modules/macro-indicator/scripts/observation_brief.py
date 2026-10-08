"""Natural-language observation coverage; never infers cycle stages."""
import argparse,json,math,re,datetime as dt
from pathlib import Path
from urllib.parse import urlparse

def brief(data):
 rows=data.get('indicators')
 if not isinstance(rows,list) or not rows:raise ValueError('指标清单为空')
 lines=['# 宏观观测资料说明','','本次展示实际保存的观测，不据此判断四周期阶段。月份、季度、年度及累计口径分别保留，不能直接混成同月结论。','','| 指标 | 观测值 | 单位 | 数据所属期 | 官方发布日期 |','|---|---|---|---|---|'];available=[];missing=[];seen=set()
 def cell(value):return str(value).replace('|','\\|').replace('\n',' ')
 for row in rows:
  if row['id'] in seen:raise ValueError('指标重复')
  seen.add(row['id']);value=row.get('value')
  if value is None:missing.append(row);continue
  if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):raise ValueError('指标数值无效')
  period=row.get('data_period');source=row.get('sourceUrl');released=row.get('official_release_date')
  if not isinstance(period,str) or not re.fullmatch(r'\d{4}(?:-(?:0[1-9]|1[0-2])|-Q[1-4])?',period):raise ValueError('所属期缺失或无效')
  parsed=urlparse(source or '')
  if parsed.scheme!='https' or parsed.hostname!='www.stats.gov.cn' or parsed.username or parsed.password:raise ValueError('该官方观测入口来源缺失或不匹配')
  if released is not None:dt.date.fromisoformat(released)
  lines.append('| '+' | '.join(cell(x) for x in [row['name'],value,row.get('unit','未确认'),period,released or '未确认'])+' |');available.append(row)
 lines[2:2]=[f'共{len(rows)}项定义，{len(available)}项有观测，{len(missing)}项尚缺。数量不代表历史完整或每项数值已独立重核。','']
 lines+=['','## 本次缺口']
 for row in missing:lines.append('- '+cell(row['name'])+'：'+cell(row.get('missing') or '尚未取得可用观测')+'。未填零或用其他指标替代。')
 lines+=['','## 来源与时点']
 for source in dict.fromkeys(row['sourceUrl'] for row in available):lines.append('- [官方公告来源]('+source+')')
 for row in available:
  if row.get('refreshStatus')=='history-only-updated':lines.append('- '+cell(row['name'])+'本次仅补充历史期间，最新观测仍沿用原获取时点，未计入最新观测刷新数量。')
  latest=next((h for h in row.get('history',[]) if h.get('period')==row.get('data_period')),{})
  if latest.get('releaseDateBasis')=='retained-prior-unchanged-value':lines.append('- '+cell(row['name'])+'发布日期沿用此前同值观测的记录，本次公告未独立确认该日期；不能当作本次重新核验通过。')
  if row.get('fetch_error'):lines.append('- '+cell(row['name'])+'刷新未完成，保留旧观测及原时间：'+cell(row['fetch_error']))
  if row.get('official_release_date') is None:lines.append('- '+cell(row['name'])+'未确认该所属期的首次官方发布日期，未用抓取日期补填。')
 for warning in data.get('maintenanceWarnings',[]):lines.append('- '+cell(warning))
 lines+=['','抓取时间只说明本地获取时点，不替代数据所属期或官方发布日期。官方公告返回观测仍需核对具体口径及跨期修订；历史覆盖不足，不输出周期阶段、可靠度百分比或资产配置指令。']
 return '\n'.join(lines)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('--out',required=True,type=Path);a=p.parse_args()
 if a.out.exists():raise FileExistsError('输出已存在，请另存研究快照')
 text=brief(json.loads(Path(a.input).read_text('utf-8-sig')));a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(text,'utf-8')
