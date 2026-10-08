"""Collect dated constituent financial facts; third-party, not announcement verification."""
import argparse,datetime as dt,json,urllib.request,urllib.parse,hashlib
from pathlib import Path
def collect(input_file,out,period):
    d=json.loads(Path(input_file).read_text(encoding='utf-8-sig'));cut=dt.date.fromisoformat(d['asOf']);dt.date.fromisoformat(period)
    universe={r['code'] for p in [d['current'],d['candidate']] for r in p['constituents']['value']};records=[];sources=[];page=1
    while True:
        p={'reportName':'RPT_F10_FINANCE_MAINFINADATA','columns':'ALL','filter':"(REPORT_DATE='"+period+"')",'pageSize':5000,'pageNumber':page}
        url='https://datacenter.eastmoney.com/api/data/v1/get?'+urllib.parse.urlencode(p)
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=25) as f:blob=f.read()
        raw=json.loads(blob);result=raw.get('result')
        if not result or not result.get('data'):raise ValueError('财务接口未返回有效同报告期记录')
        sources.append({'url':url,'sha256':hashlib.sha256(blob).hexdigest()})
        for r in result['data']:
            if r.get('SECURITY_CODE') not in universe or r.get('CURRENCY')!='CNY':continue
            observed=str(r.get('REPORT_DATE',''))[:10];published=str(r.get('NOTICE_DATE',''))[:10]
            try:
                if dt.date.fromisoformat(observed)>cut or dt.date.fromisoformat(published)>cut or observed!=period:continue
            except ValueError:continue
            records.append({'code':r['SECURITY_CODE'],'period':observed,'publishedAt':published,'netProfit':r.get('PARENTNETPROFIT'),'operatingCashPerShare':r.get('MGJYXJJE'),'revenue':r.get('TOTALOPERATEREVE'),'roePct':r.get('ROEJQ'),'orgType':r.get('ORG_TYPE')})
        if page>=int(result['pages']):break
        page+=1
        if page>10:raise ValueError('财务接口页数异常')
    # Multiple revisions at a given period must be reconciled explicitly, not overwritten.
    if len({r['code'] for r in records})!=len(records):raise ValueError('同公司同报告期存在多个版本，须核对修订')
    data={'value':records,'sourceUrl':sources[0]['url'],'sources':sources,'observedAt':period,'availableAt':d['asOf'],'retrievedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'locator':'归母净利润PARENTNETPROFIT（元）；经营现金流每股MGJYXJJE（元/股）仅用于符号，不当现金总额；NOTICE_DATE逐公司过滤；当前成分×同财报期，非历史时点成分','verification':'third-party-observed','unit':'CNY'}
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2,allow_nan=False)
    return {'records':len(records),'constituents':len(universe),'pages':page,'output':str(out)}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('--out',required=True);p.add_argument('--period',required=True);a=p.parse_args();print(json.dumps(collect(a.input,a.out,a.period),ensure_ascii=False))
