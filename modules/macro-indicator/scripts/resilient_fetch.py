"""Bounded retries with measured request counts and per-source timeouts."""
import time,urllib.request,urllib.error,ssl

class FetchError(RuntimeError):
 def __init__(self,message,attempts):
  super().__init__(message);self.attempts=attempts

def get_text(url,timeout=25,delays=(1,2,4),opener=None,sleeper=None,metrics=None,method='GET',data=None):
 opener=opener or urllib.request.urlopen;sleeper=sleeper or time.sleep
 if isinstance(timeout,bool) or not isinstance(timeout,(int,float)) or not 0<timeout<=60:raise ValueError('timeout须为0至60秒之间的数值')
 if not isinstance(delays,(tuple,list)) or len(delays)>3 or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not 0<=x<=30 for x in delays):raise ValueError('退避参数最多3项，每项0至30秒')
 for attempt in range(1,len(delays)+2):
  if metrics is not None:metrics.update(attempts=attempt,timeout=timeout,success=False)
  try:
   with opener(urllib.request.Request(url,data=data,method=method,headers={'User-Agent':'Mozilla/5.0'}),timeout=timeout) as response:
    raw=response.read(8*1024*1024+1)
    if len(raw)>8*1024*1024:raise ValueError('公告响应超过8MiB限制')
    text=raw.decode('utf-8-sig')
   if metrics is not None:metrics['success']=True
   return text
  except Exception as error:
   retryable=isinstance(error,(TimeoutError,ConnectionError))
   if isinstance(error,urllib.error.HTTPError):retryable=error.code in [408,500,502,503,504]
   elif isinstance(error,urllib.error.URLError):retryable=not isinstance(error.reason,ssl.SSLError)
   if metrics is not None:metrics['retryable']=retryable;metrics['errorType']=type(error).__name__
   if retryable and attempt<=len(delays):sleeper(delays[attempt-1])
   else:raise FetchError(('重试耗尽：' if retryable else '不重试：')+str(error),attempt) from error
