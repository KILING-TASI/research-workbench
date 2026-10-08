import json,re,urllib.request,datetime,concurrent.futures,html,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/'assets/selection-data.json'
def num(v):
 try:
  result=float(v);return result if math.isfinite(result) else None
 except (ValueError,TypeError):return None
def refresh(codes=None):
 text=(ROOT/'assets/selection-ui.js').read_text(encoding='utf8');defaults=sorted(set(re.findall(r"['\"]?code['\"]?\s*:\s*['\"](\d{6})",text)))
 codes=sorted(set(codes or defaults))
 universe={r['code'] for r in json.loads((ROOT/'assets/market-official.json').read_text(encoding='utf8'))['rows']}
 if not codes or any(not re.fullmatch(r'\d{6}',c) or c not in universe for c in codes):raise ValueError('ETF code absent from official product universe')
 old=json.loads(PATH.read_text(encoding='utf8')) if PATH.exists() else {'rows':{}};errors=[]
 symbols=[('sh' if c.startswith('5') else 'sz')+c for c in codes]
 try:
  req=urllib.request.Request('https://qt.gtimg.cn/q='+','.join(symbols),headers={'User-Agent':'Mozilla/5.0','Referer':'https://gu.qq.com/'})
  with urllib.request.urlopen(req,timeout=20) as response:raw=response.read().decode('gb18030')
  for c in codes:
   match=re.search(r'v_(?:sh|sz)'+c+r'="([^"]*)"',raw)
   if not match:errors.append(c+': missing quote');continue
   f=match[1].split('~')
   if len(f)<38 or not re.fullmatch(r'\d{14}',f[30]):errors.append(c+': missing timestamp');continue
   timestamp=datetime.datetime.strptime(f[30],'%Y%m%d%H%M%S').replace(tzinfo=datetime.timezone(datetime.timedelta(hours=8))).isoformat()
   bid,ask=num(f[9]),num(f[19]);amount=None;parts=f[35].split('/')
   if len(parts)==3:
    candidate,check=num(parts[2]),num(f[37])
    if candidate is not None and check is not None and candidate>=0 and abs(candidate-check*10000)<=10000:amount=candidate
   old['rows'][c]={**old['rows'].get(c,{}),'asOf':timestamp[:10],'quoteAt':timestamp,'dayAmount':amount,'spread':(ask-bid)/((ask+bid)/2)*100 if bid and ask and 0<bid<=ask else None,'source':'https://qt.gtimg.cn/','bid':bid,'ask':ask}
 except Exception as e:errors.append(type(e).__name__+': '+str(e))
 managers={**{c:'https://www.efunds.com.cn/en/fund/'+c+'.shtml' for c in ['510310','510580','510100','515180','563000','588080']},**{c:'https://fund.chinaamc.com/fund/'+c+'/jijinfeilv.shtml' for c in ['510330','512500','510050','588000','515070','512950']}}
 def fee_fetch(item):
  code,url=item
  try:
   with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=15) as response:blob=response.read()
   try:page=blob.decode('utf8')
   except UnicodeDecodeError:page=blob.decode('gb18030')
   plain=html.unescape(re.sub('<[^>]+>',' ',page));plain=re.sub(r'\s+',' ',plain)
   management=re.search(r'(?:基金管理费|Management Fee)\s+([0-9.]+)\s*%',plain);custody=re.search(r'(?:基金托管费|Custody Fee)\s+([0-9.]+)\s*%',plain)
   if not management or not custody:return code,None,'fee fields unavailable'
   m,c=float(management[1]),float(custody[1])
   if not(0<=m<=3 and 0<=c<=1):return code,None,'invalid fee range'
   return code,{'management':m,'custody':c,'checkedAt':datetime.date.today().isoformat(),'effectiveAt':None,'source':url},None
  except Exception as e:return code,None,type(e).__name__
 for code,fee,error in concurrent.futures.ThreadPoolExecutor(3).map(fee_fetch,[(c,u) for c,u in managers.items() if c in codes]):
  if fee:old.setdefault('fees',{})[code]=fee
  else:errors.append(code+': '+error)
 old['attemptedAt']=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat();old['errors']=errors;PATH.write_text(json.dumps(old,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8');print(json.dumps({'codes':len(codes),'rows':len(old['rows']),'errors':errors}))
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--codes');args=p.parse_args();refresh(args.codes.split(',') if args.codes else None)
