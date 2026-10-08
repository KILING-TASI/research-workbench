"""Compare observations with an explicitly scoped, sourced calendar; do not fill gaps."""
import hashlib,json
from collection_validation import day
from research_brief_html import safe_url

def validate(calendar,start,end,market=None):
    if not isinstance(calendar,dict):raise ValueError('日历须为对象')
    if not safe_url(calendar.get('sourceUrl')) or not calendar['sourceUrl'].startswith('https://'):raise ValueError('日历需HTTPS来源')
    if calendar.get('applicabilityConfirmed') not in (True,False) or type(calendar.get('applicabilityConfirmed')) is not bool:raise ValueError('日历需显式适用性确认')
    if not isinstance(calendar.get('market'),str) or not calendar['market']:raise ValueError('日历需市场标识')
    if market is not None and calendar['market']!=market:raise ValueError('日历市场与请求市场不一致')
    cs,ce=day(calendar.get('start')),day(calendar.get('end'))
    if cs>day(start) or ce<day(end):raise ValueError('日历范围须覆盖整个请求区间')
    dates=calendar.get('dates')
    if not isinstance(dates,list) or any(not isinstance(d,str) for d in dates) or dates!=sorted(set(dates)):raise ValueError('日历日期须为有序唯一列表')
    if any(not cs<=day(d)<=ce for d in dates):raise ValueError('日历日期越界')
    return calendar

def assess(dates,start,end,calendar=None,market=None):
    day(start);day(end)
    if start>end or dates!=sorted(set(dates)) or any(not day(start)<=day(d)<=day(end) for d in dates):raise ValueError('观测日期重复、乱序或越界')
    basic=dict(requestedStart=start,requestedEnd=end,observations=len(dates),actualStart=min(dates,default=None),actualEnd=max(dates,default=None),
               minimumReturnObservationsMet=len(dates)>=2,coveragePct=None,missingDates=None,unexpectedDates=None,status='calendar-not-provided',
               scope='日期覆盖不证明价格正确、分红正确或历史冻结；停牌及净值披露延迟需另外核查')
    if calendar is None:return basic
    validate(calendar,start,end,market)
    expected={d for d in calendar['dates'] if start<=d<=end};actual=set(dates)
    confirmed=calendar['applicabilityConfirmed']
    missing=sorted(expected-actual);extra=sorted(actual-expected)
    basic.update(status='calendar-applicability-unconfirmed' if not confirmed else 'date-gaps' if missing or extra else 'no-observation-days' if not expected else 'dates-aligned',
                 expectedObservations=len(expected),missingDates=missing,unexpectedDates=extra,
                 coveragePct=len(actual&expected)/len(expected)*100 if confirmed and expected else None,
                 lastExpectedDate=max(expected,default=None),calendarSource=calendar['sourceUrl'],calendarMarket=calendar['market'],
                 calendarSha256=hashlib.sha256(json.dumps(calendar,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
                 calendarVerification='input-declared; source and applicability require review')
    return basic

def note(result):
    if result['status']=='calendar-not-provided':return '未提供适用日历，交易日完整度未确认；不能只凭记录数判断完整。'
    if result['status']=='calendar-applicability-unconfirmed':return '日历适用性未确认，不输出完整度百分比。'
    if result['status']=='no-observation-days':return '请求区间按该日历没有预期观测日，不能把空数据算成100%完整。'
    if result['status']=='dates-aligned':return '本窗口'+str(result['expectedObservations'])+'个预期日期均有观测；日期齐备不等于数值或分红已核验。'
    return '按本次日历发现'+str(len(result['missingDates']))+'个缺少观测的日期、'+str(len(result['unexpectedDates']))+'个日历外日期；需核对停牌、披露规则或来源漏数，不补值。'
