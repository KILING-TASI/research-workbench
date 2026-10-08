"""Build calendar payload from declared sources. Does not fetch or optimize models."""
import argparse, json, re
from pathlib import Path
from announcement_versions import version_review

def quantile(values, q):
    values=sorted(values);pos=(len(values)-1)*q;lo=int(pos)
    return values[lo]+(values[min(lo+1,len(values)-1)]-values[lo])*(pos-lo)

def payload(source, overlays, model):
    old={r['code']:r for r in model.get('rows',[])};rows=[]
    for original in source['records']:
        r={k:original.get(k) for k in ['code','name','applyDate','refundDate','listingDate','price','maxShares','minShares','onlineShares','gainPct','ratePct','firstClose','approxAnnualPct']}
        r.update(paymentDate=None,issuePE=None,method=None,industry=None,applyEndDate=None)
        r['officialFieldVerification']=original.get('officialFieldVerification',{})
        r['announcements']=[{k:a.get(k) for k in ['title','date','url','source','metadataDate','bodyDate','bodyChecked','dateBasis','dateEvidence']} for a in original.get('announcements',[])]
        r['resultDates']=sorted({a['date'] for a in r['announcements'] if a.get('date') and '发行结果' in a.get('title','')})
        r.update(overlays.get('records',{}).get(r['code'],{}))
        r['announcementVersionReview']=version_review(r['announcements'])
        r['sourceConflicts']=dict(original.get('sourceConflicts',{}))
        for key,e in r.get('officialFieldVerification',{}).items():
            if e.get('status')=='original-numeric-matched' and original.get(key)!=e.get('value'):
                r['sourceConflicts'][key]={'thirdParty':original.get(key),'originalRegistered':e.get('value'),'status':'needs-review'}
        pool=sorted([x for x in source['records'] if x.get('listingDate') and r.get('applyDate') and x['listingDate']<r['applyDate'] and x.get('ratePct') and x['code']!=r['code']],key=lambda x:x['listingDate'],reverse=True)[:20]
        r['hundredReference']={'sampleCount':len(pool),'rates':{label:quantile([x['ratePct'] for x in pool],q) for label,q in [('乐观参考',.75),('中位参考',.5),('谨慎参考',.25)]},'codes':[x['code'] for x in pool]} if len(pool)>=10 else None
        if r['code'] in old:
            record=old[r['code']]
            r['oldModelReference']={'evaluatedAt':model.get('evaluatedAt'),'mode':model.get('mode'),'baseline':record['predictions']['baseline'],'window':record.get('window')}
        rows.append(r)
    return {'fetchedAt':source['fetchedAt'],'source':source['source'],'records':rows,'annualRecords':[{k:r.get(k) for k in ['code','applyDate','refundDate','listingDate','price','maxShares','minShares','ratePct','gainPct']} for r in rows]}

def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--overlays',type=Path,required=True);p.add_argument('--model',type=Path);p.add_argument('--template',type=Path,required=True);p.add_argument('--bse-calendar',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():raise ValueError('输出须为新文件，审核后再发布')
    read=lambda path:json.loads(path.read_text(encoding='utf-8'))
    model=read(a.model) if a.model is not None else {}
    d=payload(read(a.data),read(a.overlays),model)
    d['historicalModelAvailable']=bool(model)
    calendar=a.template.parent/'trading-calendar-2026.json'
    if calendar.exists():d['tradingCalendar']=read(calendar)
    bse_calendar=a.bse_calendar or a.template.parent/'bse-trading-calendar-2026.json'
    if a.bse_calendar and not bse_calendar.is_file():raise ValueError('Explicit BSE calendar is missing')
    if bse_calendar.exists():d['bseTradingCalendar']=read(bse_calendar)
    text=a.template.read_text(encoding='utf-8');pattern=r'(<script id="dataset" type="application/json">).*?(</script>)'
    if len(re.findall(pattern,text,re.S))!=1:raise ValueError('模板数据入口须唯一')
    result=re.sub(pattern,lambda m:m[1]+json.dumps(d,ensure_ascii=False,allow_nan=False).replace('<','\\u003c')+m[2],text,flags=re.S)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open('x',encoding='utf-8') as f:f.write(result)
    print(json.dumps({'status':'built-for-review','records':len(d['records']),'modelOptimizationRun':False}))
if __name__=='__main__':main()
