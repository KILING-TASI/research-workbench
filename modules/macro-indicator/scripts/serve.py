from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
import json
from urllib.parse import urlsplit
from refresh import ROOT,refresh
from build import build
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*a,**kw):super().__init__(*a,directory=str(ROOT/'assets'),**kw)
 def do_GET(self):
  if self.path=='/api/macro-refresh':
   self.reply(405,{'error':'刷新需要主动POST请求，读取页面不更新数据'},allow='POST');return
  if self.path=='/':self.path='/workbench.html'
  super().do_GET()
 def reply(self,status,value,allow=None):
  payload=json.dumps(value,ensure_ascii=False).encode('utf-8');self.send_response(status)
  self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store')
  if allow:self.send_header('Allow',allow)
  self.end_headers();self.wfile.write(payload)
 def do_POST(self):
  if self.path!='/api/macro-refresh':self.reply(404,{'error':'未知入口'});return
  host=self.headers.get('Host','');port=self.server.server_address[1]
  origin=self.headers.get('Origin');parsed=urlsplit(origin) if origin else None
  trusted=host in ['127.0.0.1:'+str(port),'localhost:'+str(port)]
  if not trusted or self.headers.get('X-Research-Action')!='macro-refresh' or origin and (parsed.scheme!='http' or parsed.netloc!=host or parsed.path or parsed.query or parsed.fragment):
   self.reply(403,{'error':'仅接受本地工作台主动刷新请求'});return
  try:
   data=refresh();build();self.reply(200,data)
  except Exception as error:self.reply(502,{'error':str(error)})
if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',8767),Handler).serve_forever()
