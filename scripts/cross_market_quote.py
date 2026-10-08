"""Explicit HK/US quote snapshots; no historical/financial coverage claims."""
import argparse,datetime as dt,json,re,math,hashlib
from pathlib import Path
from portable_collect import get
from collection_validation import day

def symbol(market,code):
 if not isinstance(code,str):raise ValueError('证券代码须为字符串')
 if market=='HK' and re.fullmatch(r'\d{5}',code):return 'hk'+code
 if market=='US' and re.fullmatch(r'[A-Z][A-Z0-9.-]{0,14}',code):return 'us'+code
 raise ValueError('市场须HK/US；港股五位代码，美股明确大写交易代码')
def parse(text,market,code,asof):
 day(asof);s=symbol(market,code);m=re.fullmatch(r'\s*v_'+re.escape(s)+r'="([^"\r\n]*)";\s*',text)
 if not m:raise ValueError('返回行情标识不匹配')
 f=m[1].split('~')
 if len(f)<37 or not f[1]:raise ValueError('返回字段不足')
 if (market=='HK' and f[2]!=code) or (market=='US' and f[2] not in (code,code+'.OQ',code+'.N',code+'.A')):raise ValueError('供应商证券代码不匹配')
 stamp=dt.datetime.strptime(f[30],'%Y/%m/%d %H:%M:%S' if market=='HK' else '%Y-%m-%d %H:%M:%S');price=float(f[3])
 if not math.isfinite(price) or price<=0:raise ValueError('行情价格无效')
 future=stamp.date().isoformat()>asof
 return dict(market=market,code=code,name=f[1],vendorCode=f[2],quote=None if future else dict(price=price,currency='HKD' if market=='HK' else 'USD',localTimestamp=stamp.isoformat(),timezone='Asia/Hong_Kong' if market=='HK' else '供应商未明确时区，不能计算行情年龄'),status='晚于截止日，已隔离' if future else '第三方行情快照，非实时承诺',sourceUrl='https://qt.gtimg.cn/q='+s,sha256=hashlib.sha256(text.encode()).hexdigest(),identityVerification='供应商代码与名称匹配，交易所类别未核验',coverage=[dict(domain='quote',status='已取得但因截止日不可用' if future else '已取得'),dict(domain='history',status='本入口未接入'),dict(domain='financialStatements',status='本入口未接入'),dict(domain='announcements',status='本入口未接入'),dict(domain='fundHoldings',status='本入口未接入')],limitations=['此接口不证明证券为股票、ETF或指数；不凭名称猜类别','跨币种价格不可直接比较或相加；需要明确汇率日期和来源','无完整历史、分时、资金流或三表自动采集承诺'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--market',required=True);p.add_argument('--code',required=True);p.add_argument('--as-of',required=True);p.add_argument('--raw');p.add_argument('--out',required=True);a=p.parse_args();out=Path(a.out)
 if out.exists() or out.with_suffix('.md').exists():raise FileExistsError('输出已存在')
 s=symbol(a.market,a.code);raw=Path(a.raw).read_text(encoding='utf-8') if a.raw else get('https://qt.gtimg.cn/q='+s,'gb18030');r=parse(raw,a.market,a.code,a.as_of);r['retrievedAt']=None if a.raw else dt.datetime.now(dt.timezone.utc).isoformat();out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');out.with_suffix('.md').write_text('\n'.join(['# 跨市场行情快照','',r['name']+'（'+r['market']+' '+r['code']+'）',r['status'],(f"价格：{r['quote']['price']} {r['quote']['currency']}；供应商当地时间：{r['quote']['localTimestamp']}。" if r['quote'] else '截止日前无可用快照'),'', '历史行情、财报、公告及持仓：本入口未接入。',r['sourceUrl']]+r['limitations']),encoding='utf-8')
