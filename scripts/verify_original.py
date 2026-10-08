"""Verify supplied official PDF identity and exact table cells. No discovery or fraud verdict."""
import argparse,datetime as dt,hashlib,json,re
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse
import pdfplumber
from collection_validation import day,unique_pairs,reject_constant,finite_json_float
from research_library import url as validate_url

def compact(s):return re.sub(r"\s+","",s or "").replace("．",".")
def date(s):return day(s)
def chinese_number(s):
    digits=dict(zip("零〇一二三四五六七八九","00123456789"))
    if s.isdigit():return int(s)
    if "十" in s:
        a,b=s.split("十");return (int(digits[a]) if a else 1)*10+(int(digits[b]) if b else 0)
    return int("".join(digits[x] for x in s))
def dates_in(text):
    result=[]
    for y,m,d in re.findall(r"([0-9零〇一二三四五六七八九]{4})年([0-9一二三四五六七八九十]+)月([0-9一二三四五六七八九十]+)日",compact(text)):
        try:found=dt.date(chinese_number(y),chinese_number(m),chinese_number(d)).isoformat()
        except (ValueError,KeyError):continue  # Merged PDF columns can produce non-date tokens.
        result.append(found)
    return result

def verify(request):
    if request.get('schemaVersion')==2:
        from original_layouts import verify_v2
        return verify_v2(request)
    for key in ['documentPath','sourceUrl','trustedPublisherHosts','sha256','title','issuer','reportDate','publishedAt','asOf','publicationExcerpt','fields']:
        if key not in request:raise ValueError('缺少:'+key)
    for key in ['title','issuer','publicationExcerpt','sourceUrl']:
        if not isinstance(request[key],str) or not compact(request[key]):raise ValueError('身份与摘录不得为空:'+key)
    if not isinstance(request['trustedPublisherHosts'],list) or not request['trustedPublisherHosts']:raise ValueError('官方域名清单须为非空列表')
    validate_url(request['sourceUrl']);host=urlparse(request['sourceUrl']).hostname
    if urlparse(request['sourceUrl']).scheme!='https' or host not in request['trustedPublisherHosts']:raise ValueError('来源不在明确核对的官方域名清单')
    if not date(request['reportDate'])<=date(request['publishedAt'])<=date(request['asOf']):raise ValueError('日期越界')
    blob=Path(request['documentPath']).read_bytes();digest=hashlib.sha256(blob).hexdigest()
    if not blob.startswith(b'%PDF') or digest!=request['sha256']:raise ValueError('PDF内容或哈希不符')
    fields=request['fields']
    if not isinstance(fields,list) or not fields:raise ValueError('缺少待核验字段')
    with pdfplumber.open(request['documentPath']) as doc:
        front=''.join(compact(p.extract_text()) for p in doc.pages[:8])
        for name in ['title','issuer','publicationExcerpt']:
            if compact(request[name]) not in front:raise ValueError('原文身份/发布日期摘录不符:'+name)
        if request['publishedAt'] not in dates_in(request['publicationExcerpt']):raise ValueError('发布日期与摘录不符')
        if request['reportDate'] not in dates_in(front):raise ValueError('报告期未找到')
        verified=[];seen=set();table_cache={}
        for field in fields:
            if not isinstance(field,dict):raise ValueError('待核验字段须为对象')
            key=field['id']
            if not isinstance(key,str) or not key.strip() or not isinstance(field.get('label'),str) or not compact(field['label']):raise ValueError('字段ID与行标签不得为空')
            if key in seen:raise ValueError('重复字段')
            seen.add(key);page=field['page'];column=field['column'];value=Decimal(str(field['value']))
            if isinstance(page,bool) or not isinstance(page,int) or not 1<=page<=len(doc.pages):raise ValueError('无效页码')
            if not isinstance(column,int) or isinstance(column,bool) or column<0 or not value.is_finite():raise ValueError('无效列或金额')
            if field.get('unit')!='CNY' or field.get('period')!=request['reportDate']:raise ValueError('单位/报告期未明确匹配')
            matches=[]; candidates=[]
            if page not in table_cache:table_cache[page]=doc.pages[page-1].extract_tables()
            for table in table_cache[page]:
                for row in table:
                    if not row or compact(row[0])!=compact(field['label']):continue
                    if column>=len(row):continue
                    candidates.append(row)
                    token=compact(row[column]).replace(',','')
                    if token=='-':
                        if field.get('reportedEmpty') is not True:continue
                        amount=Decimal(0)
                    else:
                        if field.get('reportedEmpty') is True:continue
                        try:amount=Decimal(token)
                        except Exception:continue
                    if amount==value:matches.append(row)
            if len(candidates)!=1 or len(matches)!=1:raise ValueError('字段原文行列匹配缺失或不唯一:'+key)
            verified.append({**field,'originalRow':matches[0],'verification':'exact-table-cell'})
    return {'type':'original-document-verification','status':'passed','sourceUrl':request['sourceUrl'],'sha256':digest,'title':request['title'],'issuer':request['issuer'],'reportDate':request['reportDate'],'publishedAt':request['publishedAt'],'fields':verified,'limitations':['只核验列出的字段与当前文件，不证明其他字段或财务真实性','官方域名清单由调用者核对，未自动发现公告','送出日期不等于已取得当时网络发布快照；当前原文不是历史冻结预测输入']}

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('input');a.add_argument('--out',required=True);v=a.parse_args()
    if Path(v.out).exists():raise FileExistsError('输出已存在')
    input_path=Path(v.input).resolve();request=json.loads(input_path.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)
    if isinstance(request,dict) and isinstance(request.get('documentPath'),str):
        path=Path(request['documentPath']);request['documentPath']=str(path if path.is_absolute() else input_path.parent/path)
    r=verify(request)
    with Path(v.out).open('x',encoding='utf8') as f:json.dump(r,f,ensure_ascii=False,indent=2)
