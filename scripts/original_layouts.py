"""Scoped native table/text evidence; automatic OCR is not supported."""
import datetime as dt
import hashlib
import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse
import pdfplumber
from collection_validation import day
from research_library import url as validate_url

def norm(value):
    return re.sub(r'\s+','',unicodedata.normalize('NFKC',str(value or '')))

def number(token):
    s=norm(token).replace(',','').replace('−','-')
    if s.startswith('(') and s.endswith(')'):s='-'+s[1:-1]
    v=Decimal(s)
    if not v.is_finite():raise ValueError('非有限数值')
    return v

def present_date(text,day):
    from verify_original import dates_in
    return day in dates_in(text) or day in re.findall(r'\d{4}-\d{2}-\d{2}',text)

def ocr_page(path,page,settings):
    raise RuntimeError('内置自动OCR已移除；扫描件请提供人工复核资料')

def tables_for(page,layout):
    if layout=='lines':return page.extract_tables()
    if layout=='text':return page.extract_tables({'vertical_strategy':'text','horizontal_strategy':'text','min_words_vertical':2})
    raise ValueError('tableLayout仅支持lines/text；不自动混用多套结果')

def check_field(field,page,text,ocr):
    result={'id':field.get('id'),'page':field.get('page'),'label':field.get('label'),
            'unitText':field.get('unitText'),'periodText':field.get('periodText'),
            'status':'unverified','candidates':[]}
    if not isinstance(field.get('label'),str) or not norm(field['label']):raise ValueError('缺少label')
    # Coordinates are PDF points; explicit scope resolves consolidated/parent or other repeated tables.
    scope=page
    if field.get('bbox') is not None:
        box=field['bbox']
        if not isinstance(box,list) or len(box)!=4 or any(type(v) not in [int,float] for v in box):raise ValueError('bbox须为四个坐标')
        scope=page.crop(tuple(box),strict=True)
        if ocr:raise ValueError('OCR暂不支持bbox精确坐标核验，请提供完整摘录复核')
        text=scope.extract_text() or ''
    mode=field.get('mode','table')
    if mode=='text':
        excerpt=field.get('excerpt')
        if not isinstance(excerpt,str) or not norm(excerpt):raise ValueError('正文核验必须提供完整excerpt')
        count=norm(text).count(norm(excerpt))
        result['candidateCount']=count;result['excerpt']=excerpt
        if count!=1:result['status']='ambiguous' if count>1 else 'missing';return result
        if norm(field['label']) not in norm(excerpt):raise ValueError('摘录不包含字段标签')
        if field.get('value') is not None:
            wanted=number(field['value'])
            tokens=re.findall(r'(?<![\d.])\(?[-−]?\d[\d,]*(?:\.\d+)?\)?',unicodedata.normalize('NFKC',excerpt))
            values=[]
            for token in tokens:
                try:values.append(number(token))
                except InvalidOperation:pass
            if wanted not in values:result['status']='mismatch';return result
            for name in ['unitText','periodText']:
                if not norm(field.get(name)) or norm(field[name]) not in norm(excerpt):raise ValueError('数值摘录缺单位或期间:'+name)
        result['status']='needs-review' if ocr else 'matched'
        result['verification']='ocr-excerpt-candidate' if ocr else 'native-exact-excerpt'
        return result
    if mode!='table':raise ValueError('mode须为table或text')
    if ocr:
        result.update(status='needs-review',reason='扫描表格尚不能可靠重建列关系；请人工复核或改用正文摘录',ocrText=text)
        return result
    for name in ['columnHeader','unitText','periodText']:
        if not norm(field.get(name)):raise ValueError('表格核验缺少:'+name)
    tables=tables_for(scope,field.get('tableLayout','lines'))
    label_col=field.get('labelColumn',0);column=field.get('column')
    if type(column)!=int or column<0 or type(label_col)!=int or label_col<0:raise ValueError('无效列编号')
    all_candidates=[]
    for ti,table in enumerate(tables):
        for ri,row in enumerate(table):
            if label_col<len(row) and norm(row[label_col])==norm(field['label']):
                all_candidates.append({'tableIndex':ti,'rowIndex':ri,'row':row})
    result['candidates']=all_candidates
    selected=all_candidates
    if 'tableIndex' in field:
        if type(field['tableIndex'])!=int or not 0<=field['tableIndex']<len(tables):raise ValueError('tableIndex越界')
        selected=[c for c in selected if c['tableIndex']==field['tableIndex']]
    if len(selected)!=1:
        result['status']='ambiguous' if len(selected)>1 else 'missing';return result
    candidate=selected[0];table=tables[candidate['tableIndex']];row=candidate['row']
    headers=''.join(norm(r[column]) for r in table[:candidate['rowIndex']] if column<len(r))
    if norm(field['columnHeader']) not in headers:result.update(status='context-mismatch',reason='目标列上方未找到指定列头');return result
    # Units and periods must be observable in the selected scope, never inferred or converted silently.
    if any(norm(field[name]) not in norm(text) for name in ['unitText','periodText']):
        result.update(status='context-mismatch',reason='选定范围未找到单位或期间');return result
    if column>=len(row):result['status']='missing';return result
    token=row[column]
    if norm(token) in ['-','—','–','']:
        result.update(status='reported-empty',originalRow=row);return result
    try:actual=number(token);expected=number(field['value'])
    except (InvalidOperation,ValueError):result.update(status='unparseable',originalRow=row);return result
    result.update(status='matched' if actual==expected else 'mismatch',originalRow=row,actual=str(actual),verification='native-scoped-table-cell')
    return result

def verify_v2(request):
    required=['documentPath','sourceUrl','trustedPublisherHosts','sha256','title','issuer','publishedAt','asOf','publicationExcerpt','fields']
    for name in required:
        if name not in request:raise ValueError('缺少:'+name)
    for name in ['title','issuer','publicationExcerpt']:
        if not isinstance(request[name],str) or not norm(request[name]):raise ValueError('空身份:'+name)
    validate_url(request['sourceUrl']);url=urlparse(request['sourceUrl']);hosts=request['trustedPublisherHosts']
    if not isinstance(hosts,list) or not hosts or url.scheme!='https' or url.hostname not in hosts:raise ValueError('来源域名未明确核对')
    if day(request['publishedAt'])>day(request['asOf']):raise ValueError('发布日期越界')
    if request.get('reportDate') is not None and day(request['reportDate'])>day(request['publishedAt']):raise ValueError('报告日期越界')
    if not present_date(request['publicationExcerpt'],request['publishedAt']):raise ValueError('发布日期与摘录不符')
    path=Path(request['documentPath']);blob=path.read_bytes();digest=hashlib.sha256(blob).hexdigest()
    if not blob.startswith(b'%PDF') or digest!=request['sha256']:raise ValueError('PDF哈希不符')
    fields=request['fields']
    if not isinstance(fields,list) or not fields or any(not isinstance(f,dict) for f in fields):raise ValueError('字段须为非空对象列表')
    ids=[f.get('id') for f in fields]
    if any(not isinstance(i,str) or not i.strip() for i in ids) or len(set(ids))!=len(ids):raise ValueError('字段ID为空或重复')
    settings=request.get('ocr',{});used=[];errors=[];texts={};results=[]
    if not isinstance(settings,dict) or type(settings.get('enabled',False))!=bool:raise ValueError('OCR配置无效')
    if settings.get('enabled') or settings.get('executable') or settings.get('renderer') or settings.get('pages'):
        raise ValueError('内置自动OCR已移除；请人工复核扫描件，不接受OCR程序配置')
    with pdfplumber.open(path) as doc:
        identity=request.get('identityPages',list(range(1,min(8,len(doc.pages))+1)))
        if not isinstance(identity,list) or not identity or any(type(p)!=int for p in identity) or len(identity)!=len(set(identity)):raise ValueError('身份页须为非空且不重复的整数列表')
        pages=set(identity+[f.get('page') for f in fields])
        if any(type(p)!=int or not 1<=p<=len(doc.pages) for p in pages):raise ValueError('页码越界')
        for p in sorted(pages):
            texts[p]=doc.pages[p-1].extract_text() or ''
        front='\n'.join(texts[p] for p in identity)
        missing=[n for n in ['title','issuer','publicationExcerpt'] if norm(request[n]) not in norm(front)]
        if request.get('reportDate') and not present_date(front,request['reportDate']):missing.append('reportDate')
        for field in fields:
            try:result=check_field(field,doc.pages[field['page']-1],texts[field['page']],field['page'] in used)
            except Exception as exc:result={'id':field['id'],'page':field['page'],'status':'invalid','reason':str(exc)}
            results.append(result)
    passed=not missing and not used and not errors and all(r['status']=='matched' for r in results)
    return {'type':'original-document-verification','schemaVersion':2,'status':'passed' if passed else 'needs-review',
        'sourceUrl':request['sourceUrl'],'sha256':digest,'title':request['title'],'issuer':request['issuer'],
        'reportDate':request.get('reportDate'),'publishedAt':request['publishedAt'],
        'identityMissing':missing,'identityVerified':not missing and not any(p in used for p in identity),
        'ocrPages':used,'errors':errors,'fields':results,
        'limitations':['仅核验给定字段、页码与选定范围，不证明整份报告或财务真实性',
            '扫描件或图片型PDF的提取效果有限，缺少可读取原文时需人工复核，不以空白替代匹配',
            '无边框表格和合并单元格需明确布局、列头、单位及期间；跨页表头须人工定位',
            '域名由调用者核对；未自动核实网页首次发布日期；公告文本匹配不证明事件已实施']}
