"""Descriptive event-date price comparison; no causal inference or timing signal."""
import json,hashlib,datetime as dt,argparse,math
from pathlib import Path
from macro_asset_observation import build
from research_brief_html import render
from collection_validation import day,unique_pairs,reject_constant
from fund_series_tools import source

def event_clock(spec,cutoff):
 event=dt.date.fromisoformat(spec['eventDate']);publication=spec.get('publicationDate');timestamp=spec.get('publishedAt');zone=spec.get('marketTimezone')
 if timestamp:
  from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
  if not isinstance(timestamp,str) or not isinstance(zone,str):raise ValueError('带时刻的公告须声明市场时区')
  instant=dt.datetime.fromisoformat(timestamp.replace('Z','+00:00'))
  if instant.tzinfo is None or instant.utcoffset() is None:raise ValueError('公告时刻须包含时区偏移')
  try:market_date=instant.astimezone(ZoneInfo(zone)).date()
  except ZoneInfoNotFoundError:raise ValueError('市场时区无法解析，不能猜测日期')
  if publication and dt.date.fromisoformat(publication)!=market_date:raise ValueError('披露日期与公告时刻在市场时区对应日期冲突')
  publication=market_date.isoformat()
 elif zone:raise ValueError('市场时区仅与明确公告时刻一同提供')
 known=dt.date.fromisoformat(publication) if publication else event
 if known>cutoff:raise ValueError('公告披露晚于研究截止日，不能用于此前复盘')
 reference=max(event,known)
 return dict(eventDate=event.isoformat(),publicationDate=publication,publishedAt=timestamp,marketTimezone=zone,alignmentDate=reference.isoformat(),afterPolicy='first-common-date-strictly-after-reference' if timestamp else 'first-common-date-on-or-after-reference',status='input-declared-not-first-publication-verified',limitation='有公告时刻时采用保守的后续日期收盘，不判断盘中、盘后及提前收市；不捕捉即时反应。')

def window_calendar(dates):
 gaps=[(dt.date.fromisoformat(b)-dt.date.fromisoformat(a)).days for a,b in zip(dates,dates[1:])]
 maximum=max(gaps,default=0)
 return dict(commonObservationDates=dates,maximumCalendarGapDays=maximum,continuityStatus='sparse-observations-not-daily-window' if maximum>7 else 'observed-dates-only-calendar-not-verified')

def run(spec,out):
 if not isinstance(spec,dict):raise ValueError('事件复盘请求须为对象')
 for key in ['archive','assetId','comparisonId']:
  if not isinstance(spec.get(key),str) or not spec[key].strip():raise ValueError('事件复盘缺少'+key)
 out=Path(out)
 if out.exists():raise FileExistsError('输出已存在')
 date=day(spec.get('eventDate'));source(spec.get('eventSourceUrl'))
 if spec['assetId']==spec['comparisonId']:raise ValueError('研究资产与对照资产不能相同')
 archive=Path(spec['archive']);data=json.loads(archive.read_bytes(),object_pairs_hook=unique_pairs,parse_constant=reject_constant)
 if not isinstance(data,dict) or not isinstance(data.get('series'),list) or any(not isinstance(s,dict) for s in data['series']):raise ValueError('行情档案须含序列对象数组')
 ids=[s.get('id') for s in data['series']]
 if any(not isinstance(i,str) or not i.strip() for i in ids) or len(set(ids))!=len(ids):raise ValueError('行情序列编号缺失或重复')
 cutoff=day(data.get('asOf'))
 clock=event_clock(spec,cutoff);reference=dt.date.fromisoformat(clock['alignmentDate'])
 if not dt.date.fromisoformat(data['start'])<=date<=cutoff:raise ValueError('事件日期不在资料窗口')
 by_id={s['id']:s for s in data['series'] if s['role']=='asset'}
 if any(i not in by_id or not by_id[i]['points'] for i in [spec['assetId'],spec['comparisonId']]):raise ValueError('缺少实际资产或对照价格')
 # Existing source verifier reparses raw responses before any price review.
 verified=build(dict(archive=str(archive)),out/'source-review')
 maps=[{p['date']:p['value'] for p in by_id[i]['points']} for i in [spec['assetId'],spec['comparisonId']]]
 dates=sorted(set(maps[0])&set(maps[1]));anchors=[d for d in dates if (d>reference.isoformat() if spec.get('publishedAt') else d>=reference.isoformat())]
 anchor=anchors[0] if anchors and (dt.date.fromisoformat(anchors[0])-reference).days<=7 else None
 rows=[]
 for n in [5,20]:
  row=dict(observationIntervals=n,status='insufficient-common-history',before=None,after=None)
  if anchor:
   idx=dates.index(anchor)
   for direction,key in [(-1,'before'),(1,'after')]:
    before_dates=[d for d in dates if d<reference.isoformat()]
    end_before=dates.index(before_dates[-1]) if before_dates else -1
    left,right=(end_before-n,end_before) if direction<0 else (idx,idx+n)
    if 0<=left<right<len(dates):
     start,end=dates[left],dates[right];returns=[m[end]/m[start]-1 for m in maps]
     if any(not math.isfinite(v) for v in [*returns,returns[0]-returns[1],*[v*100 for v in returns]]):raise ValueError('事件窗口价格变动计算溢出')
     row[key]=dict(start=start,end=end,calendarDays=(dt.date.fromisoformat(end)-dt.date.fromisoformat(start)).days,assetReturn=returns[0],comparisonReturn=returns[1],returnDifference=returns[0]-returns[1],inputs=[[m[start],m[end]] for m in maps],formula='endPrice/startPrice-1; difference=assetReturn-comparisonReturn',**window_calendar(dates[left:right+1]))
   row['status']='both-sides-available' if row['before'] and row['after'] else 'partial-history' if row['before'] or row['after'] else row['status']
  rows.append(row)
 result=dict(eventClock=clock,eventDate=spec['eventDate'],eventSourceUrl=spec['eventSourceUrl'],eventIdentityStatus='input-declared-not-original-verified',windowBasis='before-excludes-alignment-date;after-uses-declared-publication-policy',anchorDate=anchor,assetId=spec['assetId'],comparisonId=spec['comparisonId'],archiveSha256=hashlib.sha256(archive.read_bytes()).hexdigest(),sourceBindings=verified['sourceBindings'],windows=rows,limitations=['事件前窗口截止于事件与披露日期中较晚日期之前的最后共同观测；事件后遵守声明披露时点的保守日期规则，可能遗漏即时反应，不能称完整事件收益','日期仅按输入声明；盘中、盘后或休市发布可能影响对齐，不代表信息首次公开时刻','窗口按共同实际观测间隔，不是固定交易日；超过7自然日找不到事件后共同观测则留空','价格变化非含分红总收益；对照差额不是风险调整alpha，也不证明因果效应','不生成买卖点、价格预测或交易指令'])
 lines=['# 事件前后价格复盘','事件日期：'+spec['eventDate']+'；来源：'+spec['eventSourceUrl'],'发生日期与披露日期分列；披露日期：'+str(clock['publicationDate'] or '未单独登记')+'。日期和身份尚未完成原文核验；事件后首个共同观测日：'+str(anchor),clock['limitation'],*result['limitations']]
 if clock['publishedAt']:lines.append('登记公告时刻：'+clock['publishedAt']+'；日期对齐时区：'+clock['marketTimezone']+'。行情日期所属时区仍需另行核对，不据此确认首次公开时间。')
 for row in rows:
  lines+=['','## '+str(row['observationIntervals'])+'个共同观测间隔']
  for key,label in [('before','事件前'),('after','事件后')]:
   w=row[key]
   lines.append(label+'：'+(w['start']+'至'+w['end']+'，'+spec['assetId']+'价格变化'+format(w['assetReturn'],'.2%')+'，'+spec['comparisonId']+'变化'+format(w['comparisonReturn'],'.2%')+'，差额'+format(w['returnDifference']*100,'.2f')+'个百分点。' if w else '共同历史不足，未计算。'))
   if w:
    lines.append('上述窗口跨越'+str(w['calendarDays'])+'个自然日，最大相邻观测间隔'+str(w['maximumCalendarGapDays'])+'日；未核验完整交易日历。')
    if w['continuityStatus']=='sparse-observations-not-daily-window':lines.append('窗口存在超过7自然日的观测间隔，只能解释为稀疏观测点间价格变化，不能称为连续日度事件窗口。')
 out.mkdir(parents=True,exist_ok=True)
 text='\n\n'.join(lines);(out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');(out/'事件价格复盘.md').write_text(text,encoding='utf-8');(out/'事件价格复盘.html').write_text(render(text,title='事件前后价格复盘'),encoding='utf-8');return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out-dir',type=Path,required=True);a=p.parse_args();run(json.loads(a.input.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant),a.out_dir)
