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

def verify(request,engine_project_dir=None):
    if request.get('schemaVersion')==2:
        from original_layouts import verify_v2
        return verify_v2(request)  # Explicitly not yet migrated.
    from specialist_loader import call
    return call('financial','original_compat','verify',request,project_dir=engine_project_dir)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('input');a.add_argument('--out',required=True);v=a.parse_args()
    if Path(v.out).exists():raise FileExistsError('输出已存在')
    input_path=Path(v.input).resolve();request=json.loads(input_path.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)
    if isinstance(request,dict) and isinstance(request.get('documentPath'),str):
        path=Path(request['documentPath']);request['documentPath']=str(path if path.is_absolute() else input_path.parent/path)
    r=verify(request)
    with Path(v.out).open('x',encoding='utf8') as f:json.dump(r,f,ensure_ascii=False,indent=2)
