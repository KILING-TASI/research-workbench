import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import market_collect as m
class CacheDigest(unittest.TestCase):
 def loader(self,code,market,start,end,identity):
  identity.update(code=code,name='样本ETF',verification='third-party-code-matched');return [{'date':'2026-01-02','open':10,'close':11,'high':12,'low':9}],['https://example.org/data']
 def test_changed_name_price_or_source_is_not_reused(self):
  for field in ['name','price','source','missing']:
   with self.subTest(field=field),tempfile.TemporaryDirectory() as root,patch.object(m,'fund_announcements',side_effect=TimeoutError()):
    with patch.object(m,'history',side_effect=self.loader):m.collect_market(root,'etf','512010','2026-01-03',True,'2026-01-01')
    path=next((Path(root)/'research-data').rglob('history-*.json'));d=json.loads(path.read_text('utf-8'))
    if field=='name':d['identity']['name']='另一个名称'
    if field=='price':d['rows'][0]['close']=10.5
    if field=='source':d['sources']=['https://example.org/other']
    if field=='missing':d.pop('contentSha256')
    path.write_text(json.dumps(d),'utf-8');saved=path.read_bytes()
    with patch.object(m,'history',side_effect=TimeoutError()):out=m.collect_market(root,'etf','512010','2026-01-03',True,'2026-01-01')
    self.assertEqual(out['history'],[]);self.assertEqual(out['components']['history']['status'],'failed');self.assertEqual(path.read_bytes(),saved)
 def test_valid_saved_identity_and_time_reused(self):
  with tempfile.TemporaryDirectory() as root,patch.object(m,'fund_announcements',side_effect=TimeoutError()):
   with patch.object(m,'history',side_effect=self.loader):old=m.collect_market(root,'etf','512010','2026-01-03',True,'2026-01-01')
   with patch.object(m,'history') as fetch:new=m.collect_market(root,'etf','512010','2026-01-03',False,'2026-01-01')
   fetch.assert_not_called();self.assertEqual(old['identity'],new['identity']);self.assertEqual(old['components']['history']['retrievedAt'],new['components']['history']['retrievedAt'])
