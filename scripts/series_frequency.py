"""Conservative spacing screen, not an exchange-calendar verification."""
import datetime as dt,statistics

def inspect(dates):
 ds=[dt.date.fromisoformat(d) for d in dates]
 if ds!=sorted(set(ds)):raise ValueError('日期重复或乱序')
 gaps=[(b-a).days for a,b in zip(ds,ds[1:])]
 median=statistics.median(gaps) if gaps else None
 maximum=max(gaps) if gaps else None
 allowed=len(gaps)>=2 and median<=3 and maximum<=14
 return dict(observations=len(ds),medianCalendarGap=median,maxCalendarGap=maximum,dailyAnnualizationAllowed=allowed,calendarVerified=False,method='间隔中位数不超过3日且最长间隔不超过14日；至少3个观测',notice='间隔筛查不是交易日完整性核验；通过也不证明无缺日')
