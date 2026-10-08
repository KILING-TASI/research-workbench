"""Search explicit local market catalogs plus optional third-party identity candidates."""
import argparse,datetime as dt,json,re,urllib.request
from pathlib import Path
from urllib.parse import urlencode
from collection_validation import unique_pairs,reject_constant,finite_json_float

def search(workspace,query,kind=None,online=False,limit=20):
    if not isinstance(query,str) or not query.strip() or len(query)>100:raise ValueError('请输入1至100字符代码或名称')
    if kind not in [None,'fund','etf','stock','bond','convertible','government-bond','credit-bond']:raise ValueError('不支持品种')
    if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=100:raise ValueError('limit须为1至100')
    query=query.strip();rows=[];errors=[];coverage=[]
    specs=[('stock','outputs/stock-market/assets/data.json'),('fund','outputs/fund-market/assets/data.json'),('etf','outputs/etf-sector-rotation/assets/market-official.json')]
    for category,rel in specs:
        if kind and category!=kind:continue
        path=Path(workspace)/rel
        if not path.exists():coverage.append({'kind':category,'status':'missing-local-catalog'});continue
        try:
            data=json.loads(path.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float);catalog=data['rows']
            if not isinstance(catalog,list) or any(not isinstance(item,dict) or not isinstance(item.get('code'),str) or not item['code'].strip() or item.get('name') is not None and not isinstance(item['name'],str) for item in catalog):raise ValueError('目录身份条目结构无效')
            coverage.append({'kind':category,'status':'local-catalog','count':len(catalog)})
            for item in catalog:
                code=str(item.get('code',''));name=item.get('name') or ''
                if query not in code and query.casefold() not in name.casefold():continue
                market=item.get('exchange') or (item.get('symbol','')[:2] if item.get('symbol') else 'unspecified')
                rows.append({'code':code,'name':name,'kind':category,'market':market,'shareClass':'未核对','sourceUrl':item.get('source'),'catalogPath':str(path),'catalogAsOf':item.get('asOf'),'identityVerification':'official-catalog' if category=='etf' and item.get('source','').startswith(('https://www.sse.com.cn/','https://www.szse.cn/')) else 'catalog-not-officially-verified','match':'exact-code' if query==code else 'name-or-code-partial','dataCoverage':'仅目录身份；历史财报公告须另查'})
        except (OSError,ValueError,KeyError,TypeError) as exc:errors.append({'catalog':rel,'error':str(exc)})
    if online:
        url='https://searchapi.eastmoney.com/api/suggest/get?'+urlencode({'input':query,'type':14,'count':min(limit,50)})
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=15) as response:payload=json.loads(response.read())
            table=payload.get('QuotationCodeTable',{})
            if table.get('Status')!=0:raise ValueError('供应商检索失败')
            for item in table.get('Data') or []:
                raw_type=item.get('Classify');category='bond' if raw_type=='Bond' else 'stock' if raw_type=='AStock' else 'unclassified'
                # Vendor name/type does not establish convertible, treasury or credit classification.
                if kind in ['bond','convertible','government-bond','credit-bond'] and category!='bond':continue
                if kind in ['fund','etf','stock'] and category not in [kind,'unclassified']:continue
                rows.append({'code':item.get('Code'),'name':item.get('Name'),'kind':category,'requestedKind':kind,'market':'vendor:'+str(item.get('MktNum')),'quoteId':item.get('QuoteID'),'sourceUrl':url,'identityVerification':'third-party-candidate','vendorClassification':raw_type,'vendorSecurityType':item.get('SecurityTypeName'),'subtypeVerification':'未核对，不凭名称或代码前缀判转债/国债/信用债','match':'exact-code' if query==item.get('Code') else 'vendor-suggestion','dataCoverage':'身份候选；未证明条款、信用或报价有效'})
        except Exception as exc:errors.append({'sourceUrl':url,'error':type(exc).__name__+': '+str(exc)})
    dedup={}
    for r in rows:
        key=(r['kind'],r['market'],r['code'])
        if key not in dedup:dedup[key]=r
    rows=sorted(dedup.values(),key=lambda r:(r['match']!='exact-code',r['kind'],str(r['code'])))
    return {'type':'security-search','query':query,'requestedKind':kind,'matchedCount':len(rows),'rows':rows[:limit],'truncated':len(rows)>limit,'ambiguous':len(rows)>1,'coverage':coverage,'errors':errors,'queriedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'limitations':['目录与实时数据覆盖分开；不自动确认多候选','债券品种与份额类别未核验时保留未知','无授权债券全市场主数据；检索成功不等于可交易或数据完整']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('query');p.add_argument('--workspace',default='.');p.add_argument('--kind');p.add_argument('--online',action='store_true');p.add_argument('--limit',type=int,default=20);p.add_argument('--out',required=True);a=p.parse_args()
    if Path(a.out).exists():raise FileExistsError('拒绝覆盖首次检索结果')
    result=search(Path(a.workspace),a.query,a.kind,a.online,a.limit)
    with Path(a.out).open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
