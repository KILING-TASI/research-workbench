"""Calendar helpers restricted to the supplied verified calendar coverage."""
import datetime as dt

def is_open(date,calendar):
 day=dt.date.fromisoformat(date)
 if day.year!=calendar['year']:raise ValueError('Calendar year outside verified coverage')
 return day.weekday()<5 and not any(dt.date.fromisoformat(a)<=day<=dt.date.fromisoformat(b) for a,b in calendar['closedRanges'])

def next_open(date,calendar):
 day=dt.date.fromisoformat(date)+dt.timedelta(days=1)
 while not is_open(day.isoformat(),calendar):day+=dt.timedelta(days=1)
 return day.isoformat()
