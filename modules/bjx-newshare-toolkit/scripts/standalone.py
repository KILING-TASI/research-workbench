"""Independent BJX raw data and exact hundred-share threshold; no model refresh."""
import argparse
import datetime as dt
import json
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
from public_issuance_data import fetch, normalize

def threshold(price, rate, limit):
    price,rate=Decimal(price),Decimal(rate)
    if not price.is_finite() or not rate.is_finite() or price<=0 or not 0<rate<=100:
        raise ValueError('发行价须为正，配售率为百分数且须在(0,100]')
    if limit<100 or limit%100:raise ValueError('申购上限须为100股整倍数')
    shares=int((Decimal(100)/rate).to_integral_value(rounding=ROUND_CEILING))*100
    return {'shares':shares,'funds':str(price*shares),'topFunds':str(price*limit),'reachable':shares<=limit,
            'note':'给定配售率下的整手比例门槛，不承诺实际获配；配售率须由用户提供或明确预测依据'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    sub=p.add_subparsers(dest='command',required=True)
    q=sub.add_parser('threshold');q.add_argument('--price',required=True);q.add_argument('--rate-pct',required=True);q.add_argument('--max-shares',type=int,required=True)
    sub.add_parser('fetch')
    a=p.parse_args()
    if a.out.exists():raise ValueError('不覆盖已有结果，请使用新文件名')
    if a.command=='threshold':d=threshold(a.price,a.rate_pct,a.max_shares)
    else:
        raw=fetch();d=normalize(raw);d['fetchedAt']=dt.datetime.now(dt.timezone.utc).isoformat();d['verification']='第三方结构化数据，尚未逐项公告核验';d['modelOptimizationRun']=False
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open('x',encoding='utf-8') as f:json.dump(d,f,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps({'output':str(a.out)},ensure_ascii=False))
if __name__=='__main__':main()
