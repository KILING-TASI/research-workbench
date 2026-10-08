"""Independent selected ETF quote collection; no portfolio or score claims."""
import argparse
import datetime as dt
import json
import re
from pathlib import Path
from portable_collect import collect

def annotate_quote_dates(bundle):
    requested=bundle['asOf']
    for row in bundle.get('rows',[]):
        quote=row.get('quote') or {};day=quote.get('asOf')
        row['quoteDateAssessment']='same-date' if day==requested else ('different-date' if day else 'unknown')
        if day and day!=requested:
            warning='报价所属日为'+day+'，与研究截止日'+requested+'不同；不称为截止日行情或刚更新价格'
            gaps=row.setdefault('gaps',[])
            if warning not in gaps:gaps.append(warning)
    return bundle

def main():
    p=argparse.ArgumentParser();p.add_argument('--data-dir',type=Path,required=True);p.add_argument('--codes',required=True);p.add_argument('--as-of',default=dt.date.today().isoformat());p.add_argument('--out',type=Path,required=True);p.add_argument('--refresh',action='store_true');a=p.parse_args()
    codes=a.codes.split(',');dt.date.fromisoformat(a.as_of)
    if len(set(codes))!=len(codes) or any(not re.fullmatch(r'\d{6}',c) for c in codes):raise ValueError('代码须为不重复六位数字')
    if a.out.exists():raise ValueError('不覆盖已有结果')
    d=annotate_quote_dates(collect(a.data_dir,'etf',codes,a.as_of,a.refresh));a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open('x',encoding='utf-8') as f:json.dump(d,f,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps({'output':str(a.out)},ensure_ascii=False))
if __name__=='__main__':main()
