"""Public-data snapshot builder and localhost refresh server; Python stdlib only."""
import argparse
import datetime as dt
import json
import csv
import io
import subprocess
import hashlib
from pathlib import Path
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import secrets
import hmac
from announcements import enrich
from etf_embed import embed

ROOT = Path(__file__).resolve().parents[1]
API = 'https://datacenter-web.eastmoney.com/api/data/v1/get'

def fetch():
    rows = []
    page = 1
    while True:
        query = dict(reportName='RPT_NEEQ_ISSUEINFO_LIST', columns='ALL', pageSize=500,
                     pageNumber=page, sortColumns='APPLY_DATE', sortTypes='-1', source='NEEQSELECT', client='WEB')
        req = urllib.request.Request(API+'?'+urllib.parse.urlencode(query), headers={'User-Agent':'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=25) as r:
            data = json.loads(r.read().decode('utf-8-sig'))
        if not data.get('result') or not data['result'].get('data'):
            raise ValueError('数据源未返回记录，保留原快照')
        rows.extend(data['result']['data'])
        if page >= int(data['result']['pages']):
            break
        page += 1
        if page > 30:
            raise ValueError('异常分页数量')
    return rows

def normalize(rows):
    fields = dict(price='ISSUE_PRICE',totalShares='EXPECT_ISSUE_NUM',onlineShares='ONLINE_ISSUE_NUM',
                  maxShares='APPLY_NUM_UPPER',topFunds='APPLY_AMT_UPPER',ratePct='ONLINE_ISSUE_LWR',
                  gainPct='LD_CLOSE_CHANGE',firstClose='CLOSE_PRICE',profitPer100='PER_SHARES_INCOME',approxAnnualPct='CAPTURE_PROFIT',minShares='ONLINE_APPLY_LOWER',effectiveFunds='VA_AMT')
    records=[]
    for row in rows:
        rec = dict(code=str(row['SECURITY_CODE']), name=row['SECURITY_NAME_ABBR'])
        for key, field in fields.items():
            value=row.get(field)
            rec[key]=float(value) if value is not None else None
        for key, field in dict(applyDate='APPLY_DATE',listingDate='SELECT_LISTING_DATE',refundDate='ONLINE_REFUND_DATE').items():
            rec[key]=row[field][:10] if row.get(field) else None
        if not rec['listingDate']:
            rec['gainPct']=None
            rec['firstClose']=None
            rec['profitPer100']=None
            rec['approxAnnualPct']=None
        if rec['price'] and rec['maxShares'] and rec['topFunds']:
            expected=rec['price']*rec['maxShares']
            if abs(rec['topFunds']-expected)>max(2,expected*.001):
                raise ValueError('顶格资金单位校验失败: '+rec['code'])
        rec['announcementUrl']='https://data.eastmoney.com/notices/detail/'+rec['code']+'/'+str(row.get('INFO_CODE',''))+'.html'
        records.append(rec)
    return dict(fetchedAt=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(timespec='seconds'),
                source='行情与发行字段：东方财富（第三方）；公告原文优先交易所、巨潮资讯',records=records)

def save(rows):
    snapshot=normalize(rows)
    dest=ROOT/'assets'
    previous=json.loads((dest/'data.json').read_text(encoding='utf-8')) if (dest/'data.json').exists() else {}
    enrich(snapshot,previous)
    snapshot['opinions']=previous.get('opinions',[])
    snapshot['opinionSearch']=previous.get('opinionSearch',{})
    snapshot['predictionArchive']=previous.get('predictionArchive',[])
    snapshot['modelValidation']={'status':'not-run','error':'自动模型验证未执行；复盘仅记录偏差，不作为预测能力改善依据'}
    text=json.dumps(snapshot,ensure_ascii=False,allow_nan=False)
    template=(dest/'workbench.template.html').read_text(encoding='utf-8')
    engine=(dest/'engine.js').read_text(encoding='utf-8')
    page=template.replace('/*ENGINE*/',engine).replace('/*SNAPSHOT*/',text.replace('<','\\u003c'))
    page=embed(page,dest)
    # Validate everything before replacing usable snapshots.
    output=io.StringIO(newline='')
    writer=csv.writer(output)
    writer.writerow(['新股代码','名称','发行日','发行价','网上发行量','实际配售率(%)','有效申购金额(元)','首日涨跌幅(%)'])
    for rec in snapshot['records']:
        if rec['ratePct'] is not None:
            writer.writerow([rec.get(k) for k in ['code','name','applyDate','price','onlineShares','ratePct','effectiveFunds','gainPct']])
    validation_text=json.dumps(snapshot['modelValidation'],ensure_ascii=False,allow_nan=False,indent=2)
    prior_validation=dest/'模型验证.json'
    if prior_validation.is_file() and (previous.get('modelValidation') or {}).get('status')!='not-run':
        blob=prior_validation.read_bytes();archive=dest/'historical-model-validation';archive.mkdir(exist_ok=True)
        target=archive/(hashlib.sha256(blob).hexdigest()+'.json')
        if not target.exists():
            with target.open('xb') as handle:handle.write(blob)
    for name, content in [('data.json',text),('workbench.html',page),('raw.json',json.dumps(rows,ensure_ascii=False)),('北交所新股配售率样本.csv','\ufeff'+output.getvalue()),('模型验证.json',validation_text)]:
        temp=dest/(name+'.tmp')
        temp.write_text(content,encoding='utf-8')
        temp.replace(dest/name)
    return snapshot

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,directory=str(ROOT/'assets'),**kwargs)
    def do_POST(self):
        token = self.headers.get('X-Research-Token', '')
        origin = self.headers.get('Origin')
        if origin not in (None, 'http://127.0.0.1:8765') or not hmac.compare_digest(token, self.server.mutation_token):
            self.send_error(403, 'Invalid local research token'); return
        if self.path not in ('/api/refresh','/api/macro-refresh','/api/etf-refresh'):
            self.send_error(404); return
        self._authorized_mutation = True
        self.do_GET()

    def do_GET(self):
        if self.path in ('/api/refresh','/api/macro-refresh','/api/etf-refresh') and not getattr(self,'_authorized_mutation',False):
            self.send_response(405); self.send_header('Allow','POST'); self.end_headers(); return
        if self.path=='/api/macro-refresh':
            try:
                import sys
                script=ROOT.parent/'macro-indicator/scripts/refresh.py'
                subprocess.run([sys.executable,str(script)],check=True,capture_output=True,timeout=110)
                subprocess.run([sys.executable,str(script.with_name('build.py'))],check=True,capture_output=True,timeout=30)
                payload=(ROOT/'assets/macro-data.json').read_bytes();self.send_response(200)
            except Exception as e:
                payload=json.dumps({'error':str(e)},ensure_ascii=False).encode();self.send_response(502)
            self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store')
            self.end_headers();self.wfile.write(payload);return
        if self.path=='/api/etf-refresh':
            try:
                script=ROOT.parent/'etf-sector-rotation/scripts/refresh.py'
                if not script.exists():raise ValueError('ETF技能未找到，请在Codex请求更新')
                import sys
                subprocess.run([sys.executable,str(script)],check=True,capture_output=True,text=True,encoding='utf-8',timeout=240)
                subprocess.run([sys.executable,str(script.with_name('build.py'))],check=True,capture_output=True,text=True,encoding='utf-8',timeout=30)
                payload=(ROOT/'assets/etf-data.json').read_bytes();self.send_response(200)
            except Exception as e:
                payload=json.dumps({'error':str(e)},ensure_ascii=False).encode();self.send_response(502)
            self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store')
            self.end_headers();self.wfile.write(payload);return
        if self.path=='/api/refresh':
            try:
                payload=json.dumps(save(fetch()),ensure_ascii=False).encode()
                self.send_response(200)
            except Exception as e:
                payload=json.dumps({'error':str(e)},ensure_ascii=False).encode()
                self.send_response(502)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Cache-Control','no-store')
            self.end_headers(); self.wfile.write(payload)
        else:
            if self.path=='/': self.path='/workbench.html'
            super().do_GET()

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['refresh','serve','build'])
    parser.add_argument('--raw',type=Path)
    args=parser.parse_args()
    if args.mode=='serve':
        print('http://127.0.0.1:8765',flush=True)
        server=ThreadingHTTPServer(('127.0.0.1',8765),Handler)
        server.mutation_token=secrets.token_urlsafe(32)
        print('刷新接口使用 POST 和 X-Research-Token: '+server.mutation_token,flush=True)
        server.serve_forever()
    elif args.mode=='build':
        raw=json.loads(args.raw.read_text(encoding='utf-8-sig'))
        print(len(save(raw['result']['data'] if isinstance(raw,dict) else raw)['records']))
    else:
        print(len(save(fetch())['records']))
