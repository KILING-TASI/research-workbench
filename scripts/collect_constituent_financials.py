"""Collect dated constituent financial facts; third-party, not announcement verification."""
import argparse,datetime as dt,json,urllib.request,urllib.parse,hashlib,math
from pathlib import Path
from collection_validation import day,unique_pairs,reject_constant
from public_download import download
def collect(input_file,out,period):
    d=json.loads(Path(input_file).read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant)
    if not isinstance(d,dict):raise ValueError('成份财务输入须为对象')
    cut=day(d.get('asOf'))
    if day(period)>cut:raise ValueError('财务报告期晚于截止日')
    for key in ['current','candidate']:
        product=d.get(key)
        if not isinstance(product,dict) or not isinstance(product.get('constituents'),dict) or not isinstance(product['constituents'].get('value'),list) or any(not isinstance(r,dict) or not isinstance(r.get('code'),str) or not r['code'].strip() for r in product['constituents']['value']):raise ValueError('成份池须含代码对象数组')
    universe={r['code'] for p in [d['current'],d['candidate']] for r in p['constituents']['value']};records=[];sources=[];page=1
    if not universe:raise ValueError('成份池为空')
    exclusions=[]
    while True:
        p={'reportName':'RPT_F10_FINANCE_MAINFINADATA','columns':'ALL','filter':"(REPORT_DATE='"+period+"')",'pageSize':5000,'pageNumber':page}
        url='https://datacenter.eastmoney.com/api/data/v1/get?'+urllib.parse.urlencode(p)
        blob=download(url,limit=20*1024*1024,timeout=25)
        raw=json.loads(blob,object_pairs_hook=unique_pairs,parse_constant=reject_constant);result=raw.get('result') if isinstance(raw,dict) else None
        if not isinstance(result,dict) or not isinstance(result.get('data'),list) or not result['data'] or any(not isinstance(r,dict) for r in result['data']):raise ValueError('财务接口未返回有效同报告期记录')
        if type(result.get('pages')) is not int or not 1<=result['pages']<=10 or result['pages']<page:raise ValueError('财务接口页数异常')
        sources.append({'url':url,'sha256':hashlib.sha256(blob).hexdigest()})
        for r in result['data']:
            if r.get('SECURITY_CODE') not in universe:continue
            if r.get('CURRENCY')!='CNY':exclusions.append(dict(code=r['SECURITY_CODE'],reason='币种不是CNY或未披露'));continue
            observed=str(r.get('REPORT_DATE',''))[:10];published=str(r.get('NOTICE_DATE',''))[:10]
            try:
                if day(observed)>cut or day(published)>cut or observed!=period or published<observed:
                    exclusions.append(dict(code=r['SECURITY_CODE'],reason='报告期或披露日期不在合法研究范围'));continue
            except ValueError:exclusions.append(dict(code=r['SECURITY_CODE'],reason='报告期或披露日期无效'));continue
            if any(r.get(k) is not None and (isinstance(r[k],bool) or not isinstance(r[k],(int,float)) or not math.isfinite(r[k])) for k in ['PARENTNETPROFIT','MGJYXJJE','TOTALOPERATEREVE','ROEJQ']):raise ValueError('成份财务字段不是有限数值或缺失值')
            records.append({'code':r['SECURITY_CODE'],'period':observed,'publishedAt':published,'netProfit':r.get('PARENTNETPROFIT'),'operatingCashPerShare':r.get('MGJYXJJE'),'revenue':r.get('TOTALOPERATEREVE'),'roePct':r.get('ROEJQ'),'orgType':r.get('ORG_TYPE')})
        if page>=int(result['pages']):break
        page+=1
        if page>10:raise ValueError('财务接口页数异常')
    # Multiple revisions at a given period must be reconciled explicitly, not overwritten.
    if len({r['code'] for r in records})!=len(records):raise ValueError('同公司同报告期存在多个版本，须核对修订')
    missing=sorted(universe-{r['code'] for r in records})
    data={'value':records,'sourceUrl':sources[0]['url'],'sources':sources,'observedAt':period,'availableAt':d['asOf'],'retrievedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'locator':'归母净利润PARENTNETPROFIT（元）；经营现金流每股MGJYXJJE（元/股）仅用于符号，不当现金总额；NOTICE_DATE逐公司过滤；当前成分×同财报期，非历史时点成分','verification':'third-party-observed','unit':'CNY'}
    data['missingCodes']=missing;data['excludedRecords']=exclusions;data['coverageStatus']='partial' if missing else 'requested-codes-returned-not-original-verified'
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2,allow_nan=False)
    return {'records':len(records),'constituents':len(universe),'missingCodes':missing,'pages':page,'output':str(out)}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('--out',required=True);p.add_argument('--period',required=True);a=p.parse_args();print(json.dumps(collect(a.input,a.out,a.period),ensure_ascii=False))
