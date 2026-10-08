import hashlib,importlib.util,json,tempfile,unittest,datetime,types,io
from pathlib import Path
from unittest.mock import patch

def module(name):
 path=Path(__file__).resolve().parents[1]/'modules/etf-sector-rotation/scripts'/name
 spec=importlib.util.spec_from_file_location('topic_'+path.stem,path);result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result

class TopicCollectionIntegrity(unittest.TestCase):
 def test_refresh_help_and_missing_output_do_not_collect(self):
  refresh=module('refresh.py')
  with patch.object(refresh,'refresh') as collector:
   for args,exit_code in [(['--help'],0),([],2)]:
    with self.assertRaises(SystemExit) as exit:refresh.main(args)
    self.assertEqual(exit.exception.code,exit_code)
   collector.assert_not_called()
 def test_refresh_old_observations_do_not_enable_scores(self):
  refresh=module('refresh.py')
  class Clock(datetime.datetime):
   @classmethod
   def now(cls,tz=None):return cls(2026,10,8,10,0,tzinfo=tz)
  financials={f'{i:06d}':{'SECURITY_CODE':f'{i:06d}','PUBLISHNAME':'半导体','SJLTZ':10,'WEIGHTAVG_ROE':15} for i in range(1,11)}
  market={code:{'pe_ttm':20,'zllr_d5':100,'zllc_d5':50} for code in financials}
  prices=[{'date':(datetime.date(2026,7,1)+datetime.timedelta(days=i)).isoformat(),'close':1,'volume':10,'amount':1000} for i in range(70)]
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory)
   with patch.object(refresh,'ROOT',root),patch.object(refresh.dt,'datetime',Clock),patch.object(refresh,'SECTORS',[('半导体','BK1036',['510880'])]),patch.object(refresh,'financial',return_value=('2026-06-30',financials)),patch.object(refresh,'tx_market',return_value=market),patch.object(refresh,'klines',side_effect=ValueError('explicit primary failure')),patch.object(refresh,'tx_prices',return_value=('test',prices)),patch.object(refresh,'fund_info',side_effect=lambda c,t:{'code':c}):result=refresh.refresh()
   sector=result['sectors'][0];self.assertTrue(sector['stale']);self.assertTrue(sector['etfs'][0]['stale']);self.assertEqual(sector['date'],prices[-1]['date'])
 def test_price_parsers_reject_bad_dates_and_negative_prices(self):
  refresh=module('refresh.py')
  valid=[[(datetime.date(2026,7,1)+datetime.timedelta(days=i)).isoformat(),'1','1','1','1','10','1000'] for i in range(70)]
  for mutation in [None,'negative','duplicate','invalid-date']:
   rows=[r[:] for r in valid]
   if mutation=='negative':rows[10][2]='-1'
   elif mutation=='duplicate':rows[10][0]=rows[9][0]
   elif mutation=='invalid-date':rows[10][0]='2026-02-30'
   for parser,response in [('tx',{'data':{'sh510880':{'day':rows}}}),('em',{'data':{'name':'test','klines':[','.join(r) for r in rows]}})]:
    with self.subTest(mutation=mutation,parser=parser),patch.object(refresh,'js',return_value=response):
     if mutation is None:
      name,series=refresh.tx_prices('510880','2026-10-08') if parser=='tx' else refresh.klines('1.510880','2026-10-08');self.assertEqual(len(series),70)
     else:
      with self.assertRaises(ValueError):refresh.tx_prices('510880','2026-10-08') if parser=='tx' else refresh.klines('1.510880','2026-10-08')
 def test_quote_nonfinite_values_stay_missing(self):
  refresh=module('refresh_selection.py')
  for value in ['NaN','Infinity','-Infinity',None,'unknown']:self.assertIsNone(refresh.num(value))
  self.assertEqual(refresh.num('1.23'),1.23)
 def test_refresh_requires_explicit_local_post(self):
  from unittest.mock import MagicMock
  fetch=MagicMock(return_value={'ok':True});build=MagicMock()
  with patch.dict('sys.modules',{'refresh':types.SimpleNamespace(ROOT=Path('.'),refresh=fetch),'build':types.SimpleNamespace(build=build)}):server=module('serve.py')
  def handler(headers):
   value=server.Handler.__new__(server.Handler);value.path='/api/etf-refresh';value.headers=headers;value.server=types.SimpleNamespace(server_address=('127.0.0.1',8766));value.wfile=io.BytesIO();value.code=None
   value.send_response=lambda code:setattr(value,'code',code);value.send_header=lambda *a:None;value.end_headers=lambda:None;return value
  value=handler({});value.do_GET();self.assertEqual(value.code,405);fetch.assert_not_called()
  value=handler({'Host':'127.0.0.1:8766','Origin':'https://other.example','X-Research-Action':'etf-refresh'});value.do_POST();self.assertEqual(value.code,403);fetch.assert_not_called()
  value=handler({'Host':'127.0.0.1:8766','Origin':'http://127.0.0.1:8766','X-Research-Action':'etf-refresh'});value.do_POST();self.assertEqual(value.code,200);fetch.assert_called_once();build.assert_called_once()
 def test_downloaded_old_rotation_prices_are_not_fresh(self):
  with patch.dict('sys.modules',{'refresh':types.SimpleNamespace(js=lambda *a:None)}):refresh=module('refresh_rotation.py')
  class Clock(datetime.datetime):
   @classmethod
   def now(cls,tz=None):return cls(2026,10,8,10,0,tzinfo=tz)
  for bad in [None,'duplicate','nonfinite']:
   with tempfile.TemporaryDirectory() as directory:
    root=Path(directory);(root/'assets').mkdir();p=root/'assets/data.json'
    p.write_text(json.dumps({'sectors':[{'name':'红利','etfs':[{'code':'510880','name':'红利ETF','benchmark':'red'}]}],'rotationHistory':{'fresh':True,'rows':[]}}),encoding='utf-8')
    rows=[[(datetime.date(2026,9,1)+datetime.timedelta(days=i)).isoformat(),'1','1'] for i in range(30)]
    if bad=='duplicate':rows.append(rows[-1])
    if bad=='nonfinite':rows[-1][2]='Infinity'
    def response(url,params):return {'data':{params['param'].split(',')[0]:{'qfqday':rows}}}
    with patch.object(refresh,'ROOT',root),patch.object(refresh,'js',side_effect=response),patch.object(refresh.dt,'datetime',Clock):refresh.refresh()
    result=json.loads(p.read_text(encoding='utf-8'))['rotationHistory'];self.assertFalse(result['fresh'])
    if bad is None:self.assertEqual(result['freshnessStatus'],'last-trading-date-not-confirmed')
    else:self.assertTrue(result['errors'])
 def test_multiple_materials_keep_distinct_evidence_bytes(self):
  collector=module('collect_index_evidence.py')
  materials={'编制方案':[{'filePath':'https://oss-ch.csindex.com.cn/first.pdf'},{'filePath':'https://oss-ch.csindex.com.cn/second.pdf'}]}
  def request(req,timeout):
   url=req.full_url
   body=(b'%PDF-first' if url.endswith('/first.pdf') else b'%PDF-second' if url.endswith('/second.pdf') else json.dumps({'code':200,'data':materials if 'index-details-data' in url else []}).encode())
   class Response:
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self):return body
   return Response()
  with tempfile.TemporaryDirectory() as directory,patch.object(collector.urllib.request,'urlopen',side_effect=request):
   result=collector.collect(directory,'000300','2026-01-01','2026-10-08');record=json.loads(Path(result['output']).read_text(encoding='utf-8'))
   self.assertEqual(len(record['files']),2);self.assertEqual(len({r['path'] for r in record['files']}),2)
   for row in record['files']:self.assertEqual(hashlib.sha256(Path(row['path']).read_bytes()).hexdigest(),row['sha256'])
 def test_invalid_share_response_keeps_previous_sse_cache(self):
  refresh=module('refresh_market.py')
  old={'rows':[{'code':'510880','exchange':'上交所','shares':100,'asOf':'2026-10-01'}]}
  for rows in [[{'SEC_CODE':'510880','SEC_NAME':'红利','TOT_VOL':'NaN','STAT_DATE':'2026-10-08'}],[{'SEC_CODE':'510880','SEC_NAME':'红利','TOT_VOL':'100','STAT_DATE':'20261008'}],[{'SEC_CODE':'510880','SEC_NAME':'红利','TOT_VOL':'100','STAT_DATE':'2026-10-08'}]*2]:
   with tempfile.TemporaryDirectory() as directory:
    root=Path(directory);(root/'assets').mkdir();(root/'assets/market-official.json').write_text(json.dumps(old),encoding='utf-8')
    with patch.object(refresh,'ROOT',root),patch.object(refresh,'request',side_effect=[json.dumps({'result':rows}).encode(),OSError('explicit SZSE test failure')]):result=refresh.refresh()
    self.assertEqual(result['rows'],old['rows']);self.assertIn('上交所',result['errors'])

if __name__=='__main__':unittest.main()
