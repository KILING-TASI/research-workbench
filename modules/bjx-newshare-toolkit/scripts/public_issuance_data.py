"""Independent public issuance adapter; no project/model imports."""
import datetime as dt
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
API="https://datacenter-web.eastmoney.com/api/data/v1/get"

def _page(request, page, diagnostics, attempts):
    for attempt in range(1, attempts+1):
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                body=response.read(8*1024*1024+1)
            if len(body)>8*1024*1024:raise ValueError('Oversized issuance response')
            data=json.loads(body.decode('utf-8-sig'))
            diagnostics.append({'page':page,'attempt':attempt,'status':'received'})
            return data
        except urllib.error.HTTPError as error:
            retry=error.code in [408,500,502,503,504]
            diagnostics.append({'page':page,'attempt':attempt,'status':'http-error','httpCode':error.code,'retryable':retry})
            if not retry or attempt==attempts:raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            diagnostics.append({'page':page,'attempt':attempt,'status':'transport-error','errorType':type(error).__name__})
            if attempt==attempts:raise
        if attempt<attempts:time.sleep(attempt)


def fetch(diagnostics=None, attempts=3):
    if isinstance(attempts,bool) or not isinstance(attempts,int) or not 1<=attempts<=3:
        raise ValueError('Attempts must be 1..3')
    diagnostics=diagnostics if diagnostics is not None else []
    rows = []
    page = 1
    expected_pages=None
    expected_count=None
    while True:
        query = dict(reportName='RPT_NEEQ_ISSUEINFO_LIST', columns='ALL', pageSize=500,
                     pageNumber=page, sortColumns='APPLY_DATE', sortTypes='-1', source='NEEQSELECT', client='WEB')
        req = urllib.request.Request(API+'?'+urllib.parse.urlencode(query), headers={'User-Agent':'Mozilla/5.0'})
        data=_page(req,page,diagnostics,attempts)
        result=data.get('result') if isinstance(data,dict) else None
        if not isinstance(result,dict) or not isinstance(result.get('data'),list) or not result['data']:
            raise ValueError('数据源未返回记录，保留原快照')
        pages=result.get('pages')
        if isinstance(pages,str) and pages.isdigit():pages=int(pages)
        if isinstance(pages,bool) or not isinstance(pages,int) or not 1<=pages<=30:
            raise ValueError('异常分页数量，保留原快照')
        if expected_pages is not None and pages!=expected_pages:
            raise ValueError('分页总数变化，不能把混合批次当完整快照')
        expected_pages=pages
        count=result.get('count')
        if count is not None:
            if isinstance(count,str) and count.isdigit():count=int(count)
            if isinstance(count,bool) or not isinstance(count,int) or not 1<=count<=15000:raise ValueError('记录总数异常，保留原快照')
            if expected_count is not None and count!=expected_count:raise ValueError('记录总数变化，不能当完整批次')
            expected_count=count
        elif expected_count is not None:raise ValueError('分页遗漏已声明记录总数，保留原快照')
        if diagnostics and diagnostics[-1].get('status')=='received':diagnostics[-1].update(sourcePages=pages,sourceCount=count,pageRecords=len(result['data']))
        if any(not isinstance(row,dict) for row in result['data']):raise ValueError('Invalid issuance row')
        rows.extend(result['data'])
        if page >= pages:
            break
        page += 1
        if page > 30:
            raise ValueError('异常分页数量')
    if expected_count is not None and len(rows)!=expected_count:raise ValueError("实际记录数与来源总数不一致，保留原快照")
    return rows

def normalize(rows):
    fields = dict(price='ISSUE_PRICE',totalShares='EXPECT_ISSUE_NUM',onlineShares='ONLINE_ISSUE_NUM',
                  maxShares='APPLY_NUM_UPPER',topFunds='APPLY_AMT_UPPER',ratePct='ONLINE_ISSUE_LWR',
                  gainPct='LD_CLOSE_CHANGE',firstClose='CLOSE_PRICE',profitPer100='PER_SHARES_INCOME',approxAnnualPct='CAPTURE_PROFIT',minShares='ONLINE_APPLY_LOWER',effectiveFunds='VA_AMT')
    records=[]
    seen=set()
    for row in rows:
        code=row.get('SECURITY_CODE')
        if code is None or not str(code).strip():raise ValueError('缺失证券代码')
        rec = dict(code=str(code).strip(), name=row['SECURITY_NAME_ABBR'])
        if not rec['code'] or rec['code'] in seen:raise ValueError('缺失或重复证券代码')
        seen.add(rec['code'])
        for key, field in fields.items():
            value=row.get(field)
            rec[key]=float(value) if value is not None else None
            if rec[key] is not None and not math.isfinite(rec[key]):raise ValueError('非有限数值: '+rec['code']+'/'+key)
        for key, field in dict(applyDate='APPLY_DATE',listingDate='SELECT_LISTING_DATE',refundDate='ONLINE_REFUND_DATE').items():
            rec[key]=row[field][:10] if row.get(field) else None
        if not rec['listingDate']:
            rec['gainPct']=None
            rec['firstClose']=None
            rec['profitPer100']=None
            rec['approxAnnualPct']=None
        if rec['price'] and rec['maxShares'] and rec['topFunds']:
            expected=rec['price']*rec['maxShares']
            if abs(rec['topFunds']-expected)>max(2,expected*.001):
                raise ValueError('顶格资金单位校验失败: '+rec['code'])
        rec['announcementUrl']='https://data.eastmoney.com/notices/detail/'+rec['code']+'/'+str(row.get('INFO_CODE',''))+'.html'
        records.append(rec)
    return dict(fetchedAt=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(timespec='seconds'),
                source='行情与发行字段：东方财富（第三方）；公告原文优先交易所、巨潮资讯',records=records)
