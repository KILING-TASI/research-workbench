"""Versioned issuance facts matched to supplied original PDF excerpts. No model updates."""
import argparse,datetime as dt,hashlib,json,re,uuid
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

FIELDS={'price':('元/股',Decimal(1)),'onlineFinalShares':('股',Decimal(1)),
 'maxShares':('股',Decimal(1)),'refundDate':('date',None),
 'strategicShares':('股',Decimal(1)),'greenshoeShares':('股',Decimal(1)),
 'ratePct':('%',Decimal(1)), 'initialIssueShares':('股',Decimal(1)),
 'initialOnlineShares':('股',Decimal(1)), 'postIssueSharesBefore':('股',Decimal(1)),
 'postIssueSharesFull':('股',Decimal(1)), 'validSubscriptionShares':('股',Decimal(1)),
 'actualNewShares':('股',Decimal(1)), 'actualRepurchasedShares':('股',Decimal(1))}
HOSTS={'www.bse.cn','static.cninfo.com.cn','dataclouds.cninfo.com.cn'}
def compact(t):return re.sub(r'\s+','',t or '').replace('，',',')
def digest(blob):return hashlib.sha256(blob).hexdigest()
def write(path,value):
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False)
def versions(folder):
    rows=[];previous=None
    for path in sorted(folder.glob('*.json')):
        r=json.loads(path.read_text(encoding='utf-8'));h=r.pop('versionHash')
        if digest(json.dumps(r,sort_keys=True,ensure_ascii=False).encode())!=h or r['previousHash']!=previous:raise ValueError('版本链被修改')
        r['versionHash']=h;previous=h;rows.append(r)
    return rows

def register(spec,workspace):
    import pdfplumber
    for k in ['code','issuer','title','publishedAt','asOf','sourceUrl','documentPath','fields']:
        if not spec.get(k):raise ValueError('缺少:'+k)
    if not re.fullmatch(r'[0-9]{6}',spec['code']):raise ValueError('代码须六位字符串')
    if dt.date.fromisoformat(spec['publishedAt'])>dt.date.fromisoformat(spec['asOf']):raise ValueError('原文在研究截止日后披露')
    url=urlparse(spec['sourceUrl'])
    if url.scheme!='https' or url.hostname not in HOSTS:raise ValueError('原文来源域名未支持')
    blob=Path(spec['documentPath']).read_bytes()
    if len(blob)>100*1024*1024 or not blob.startswith(b'%PDF-'):raise ValueError('PDF无效或过大')
    if spec.get('sha256') and spec['sha256']!=digest(blob):raise ValueError('哈希不符')
    with pdfplumber.open(spec['documentPath']) as doc:
        texts=[compact(p.extract_text()) for p in doc.pages]
    if not all(compact(spec[k]) in ''.join(texts[:8]) for k in ['issuer','title','code']):raise ValueError('发行人、标题或代码未在原文前8页匹配')
    def page_excerpt(page,excerpt):
        if type(page)!=int or not 1<=page<=len(texts):raise ValueError('页码无效')
        e=compact(excerpt)
        if len(e)<4 or texts[page-1].count(e)!=1:raise ValueError('摘录不在指定页唯一匹配')
        return e
    publication_status='metadata-matched-not-body-publication-proof'
    if spec.get('publicationPage'):
        publication=page_excerpt(spec['publicationPage'],spec['publicationExcerpt'])
        pub=dt.date.fromisoformat(spec['publishedAt'])
        if not any(v in publication for v in [pub.isoformat(),f'{pub.year}年{pub.month}月{pub.day}日']):raise ValueError('披露日期摘录不匹配')
        publication_status='body-date-matched-not-first-web-publication-proof'
    else:
        metadata=json.loads(Path(spec['metadataPath']).read_text(encoding='utf-8-sig'))
        entries=metadata if isinstance(metadata,list) else metadata.get('announcements',[])
        matches=[r for r in entries if r.get('url')==spec['sourceUrl'] and r.get('date')==spec['publishedAt'] and r.get('issuerCode')==spec['code']]
        if len(matches)!=1:raise ValueError('披露目录日期、URL与代码未唯一匹配')
        if compact(spec['title']) not in compact(matches[0].get('title','')):raise ValueError('目录标题不符')
    facts={};known=set()
    for f in spec['fields']:
        key=f['field']
        if key not in FIELDS or key in known:raise ValueError('未知或重复字段')
        known.add(key);e=page_excerpt(f['page'],f['excerpt'])
        if not f.get('label') or compact(f['label']) not in e or not f.get('basis'):raise ValueError('标签或口径缺失')
        unit=FIELDS[key][0]
        if key=='refundDate':
            value=dt.date.fromisoformat(f['value']);day=f'{value.year}年{value.month}月{value.day}日'
            if value.isoformat() not in e and day not in e:raise ValueError('退款日期未匹配')
            normalized=value.isoformat()
        else:
            original_unit=f.get('originalUnit')
            allowed={'元/股':Decimal(1),'股':Decimal(1),'万股':Decimal(10000),'%':Decimal(1)}
            if original_unit not in allowed or (unit=='股' and original_unit not in ['股','万股']) or (unit!='股' and original_unit!=unit):raise ValueError('原文单位不一致')
            nums=re.findall(r'(?<![\d.,eE+\-−－])((?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?)'+re.escape(original_unit),e)
            # Multiple values of the same unit require a narrower unique excerpt.
            if len(nums)!=1:raise ValueError('同单位数值缺失或歧义，缩小摘录:'+key)
            value=Decimal(str(f['value']))
            if not value.is_finite() or value<0 or Decimal(nums[0].replace(',',''))*allowed[original_unit]!=value:raise ValueError('数值不符:'+key)
            if key in ['price','maxShares','onlineFinalShares'] and value<=0:raise ValueError('发行关键数值须正数')
            if unit=='股' and value!=value.to_integral_value():raise ValueError('股数须整数')
            if key=='maxShares' and value%100:raise ValueError('申购上限不是100股整数倍')
            if key=='ratePct' and value>100:raise ValueError('配售率百分数越界')
            normalized=str(value)
        facts[key]={'value':normalized,'unit':unit,'basis':f['basis'],'page':f['page'],
            'label':f['label'],'excerpt':f['excerpt'],'sourceUrl':spec['sourceUrl'],'publicationVerification':publication_status,
            'publishedAt':spec['publishedAt'],'documentSha256':digest(blob),'verification':'original-text-matched','factorEligible':False}
    folder=Path(workspace)/'research-data'/'bjx-facts'/spec['code'];vf=folder/'versions';vf.mkdir(parents=True,exist_ok=True)
    lock=folder/'write.lock'
    with lock.open('x') as handle:handle.write('locked')
    try:
        old=versions(vf)
        content={'code':spec['code'],'issuer':spec['issuer'],'title':spec['title'],'publishedAt':spec['publishedAt'],
            'sourceUrl':spec['sourceUrl'],'documentSha256':digest(blob),'facts':facts,'publicationVerification':publication_status,
            'publicationEvidence':{'metadataPath':spec.get('metadataPath'),'metadataSha256':digest(Path(spec['metadataPath']).read_bytes()) if spec.get('metadataPath') else None,'page':spec.get('publicationPage'),'excerpt':spec.get('publicationExcerpt')},
            'supersedes':spec.get('supersedes'), 'documentKind':spec.get('documentKind','unspecified')}
        signature=digest(json.dumps(content,sort_keys=True,ensure_ascii=False).encode())
        for r in old:
            if r['contentHash']==signature:return {**r,'duplicate':True}
        if spec.get('supersedes'):
            prior=next((r for r in old if r['versionHash']==spec['supersedes']),None)
            if not prior or prior['publishedAt']>spec['publishedAt']:raise ValueError('更正所指版本不存在或日期倒置')
        blobs=folder/'documents';blobs.mkdir(exist_ok=True);target=blobs/(digest(blob)+'.pdf')
        if not target.exists():target.write_bytes(blob)
        metadata_archive=None
        if spec.get('metadataPath'):
            meta_blob=Path(spec['metadataPath']).read_bytes();metadata_archive=blobs/(digest(meta_blob)+'.json')
            if not metadata_archive.exists():metadata_archive.write_bytes(meta_blob)
        r={**content,'type':'bjx-issuance-facts','contentHash':signature,'previousHash':old[-1]['versionHash'] if old else None,
            'version':len(old)+1,'recordedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'asOfAtRegistration':spec['asOf'],
            'documentPath':str(target.resolve()),'metadataArchivePath':str(metadata_archive.resolve()) if metadata_archive else None,'limitations':['仅匹配列出的原文字段，不证明其他字段','来源URL由调用者提供，未自动验证本地PDF与线上文件一致','当前文件非历史冻结预测输入']}
        r['versionHash']=digest(json.dumps(r,sort_keys=True,ensure_ascii=False).encode());write(vf/f"{r['version']:06d}.json",r)
        return r
    finally:lock.unlink()

def view(spec,workspace):
    end=dt.date.fromisoformat(spec['asOf']);code=spec['code']
    if not re.fullmatch(r'[0-9]{6}',code):raise ValueError('代码无效')
    all_rows=versions(Path(workspace)/'research-data'/'bjx-facts'/code/'versions')
    rows=[r for r in all_rows if dt.date.fromisoformat(r['publishedAt'])<=end]
    for r in rows:
        if digest(Path(r['documentPath']).read_bytes())!=r['documentSha256']:raise ValueError('归档PDF被修改')
        if r.get('metadataArchivePath') and digest(Path(r['metadataArchivePath']).read_bytes())!=r['publicationEvidence']['metadataSha256']:raise ValueError('归档披露目录被修改')
    facts={};conflicts=[]
    for key in FIELDS:
        candidates=[{'versionHash':r['versionHash'],**r['facts'][key]} for r in rows if key in r['facts']]
        replaced={r.get('supersedes') for r in rows if key in r['facts']}
        active=[c for c in candidates if c['versionHash'] not in replaced]
        signatures={(c['value'],c['basis']) for c in active}
        if len(signatures)>1:conflicts.append({'field':key,'candidates':active});facts[key]=None
        else:facts[key]=active[-1] if active else None
    return {'type':'bjx-issuance-facts-view','code':code,'asOf':spec['asOf'],'facts':facts,
        'missing':[k for k,v in facts.items() if v is None],'conflicts':conflicts,'versions':rows,
        'limitations':['不按登记先后静默覆盖冲突，更正关系是输入声明需人工核对','后披露结果只在对应截止日可见，不回填申购前事实','发行事实核对不构成获配预测或投资价值评价']}

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['register','view']);p.add_argument('input',type=Path);p.add_argument('--workspace',type=Path,default=Path.cwd());p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():raise ValueError('输出存在')
    spec=json.loads(a.input.read_text(encoding='utf-8-sig'));r=register(spec,a.workspace) if a.command=='register' else view(spec,a.workspace)
    a.out.parent.mkdir(parents=True,exist_ok=True);write(a.out,r)
if __name__=='__main__':main()
