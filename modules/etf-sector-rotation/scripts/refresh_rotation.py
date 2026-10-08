"""Refresh dated, adjusted prices for the current research observation pool."""
import concurrent.futures
import datetime as dt
import json
import math
from pathlib import Path
from refresh import js

ROOT=Path(__file__).resolve().parents[1]
def refresh():
    path=ROOT/'assets/data.json'
    data=json.loads(path.read_text(encoding='utf8'))
    now=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat()
    pool=[]; indices=set()
    for sector in data['sectors']:
        for fund in sector['etfs']:
            index=fund.get('benchmark')
            if index and index not in indices:
                pool.append(dict(symbol=fund['code'],name=fund['name'],sector=sector['name'],index=index,type='industry',eligible=True))
                indices.add(index)
                break
    errors={}
    def fetch(code):
        symbol=('sh' if code.startswith('5') else 'sz')+code
        url='https://web.ifzq.gtimg.cn/appstock/app/fqkline/get'
        item=js(url,dict(param=symbol+',day,,,180,qfq')).get('data',{}).get(symbol,{})
        rows=item.get('qfqday')
        if not rows:raise ValueError('No adjusted price series')
        result={}
        for p in rows:
            observed=p[0];value=float(p[2])
            if dt.date.fromisoformat(observed).isoformat()!=observed or not math.isfinite(value) or value<=0:raise ValueError('Invalid adjusted price date or value')
            if observed>now[:10]:continue
            if observed in result:raise ValueError('Duplicate adjusted price date')
            result[observed]=value
        if len(result)<26:raise ValueError('Insufficient history')
        return result,url+'?param='+symbol+',day,,,180,qfq'
    histories={};sources={};updated=False
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        tasks={executor.submit(fetch,code):code for code in [p['symbol'] for p in pool]+['510300']}
        for task in concurrent.futures.as_completed(tasks):
            code=tasks[task]
            try:histories[code],sources[code]=task.result()
            except Exception as e:errors[code]=str(e)
    available=[p for p in pool if p['symbol'] in histories]
    if available:
        latest=max(max(histories[p['symbol']]) for p in available)
        available=[p for p in available if max(histories[p['symbol']])==latest]
        dates=sorted(set.intersection(*(set(histories[p['symbol']]) for p in available)))
        dates=dates[-60:]
        if len(dates)>=26:
            rows=[dict(p,closes=[histories[p['symbol']][d] for d in dates]) for p in available]
            market=histories.get('510300',{})
            market_closes=[market[d] for d in dates] if all(d in market for d in dates) else []
            updated=True
            fresh=latest==now[:10]
            data['rotationHistory']=dict(verified=True,calendarAligned=True,fresh=fresh,asOf=latest,
                fetchedAt=now,dates=dates,rows=rows,marketCloses=market_closes,sources=sources,errors=errors,
                freshnessStatus='same-calendar-date' if fresh else 'last-trading-date-not-confirmed',
                verificationScope='日期、正价格、前复权字段与共同日历校验；未逐条公告核验',
                limitation='当前8行业代表ETF观察池；不是全市场排名或历史时点股票池。仓位是研究默认规则，未经收益回测。')
    if not updated and 'rotationHistory' in data:
        data['rotationHistory']['fresh']=False
        errors.setdefault('refresh', '没有获得足够的同日共同历史，保留旧缓存且不生成新信号')
    if errors and 'rotationHistory' in data:

        data['rotationHistory']['errors']=errors
        data['rotationHistory']['attemptedAt']=now
    path.write_text(json.dumps(data,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf8')
    print(json.dumps(dict(rows=len(data.get('rotationHistory',{}).get('rows',[])),errors=errors)))
if __name__=='__main__':refresh()
