import unittest,tempfile,json
from pathlib import Path
from event_research import run,monitor,start_date
import datetime as dt
class Events(unittest.TestCase):
    def spec(self,items=None):
        s={'market':'CN','code':'600036','asOf':'2026-10-03','months':1}
        if items is not None:s['items']=items
        return s
    def item(self,**changes):return {'id':'a','date':'2026-10-03','title':'关于拟回购股份的公告',**changes}
    def test_calendar(self):self.assertEqual(str(start_date(dt.date(2024,3,31),1)),'2024-02-29')
    def test_amount_not_impact(self):
        r=run(self.spec([self.item(text='拟支付2亿元，2026年10月10日开始')]),'.')['timeline'][0]
        self.assertEqual(r['amountMentions'][0]['text'],'2亿元');self.assertIsNone(r['impactAmount']);self.assertIsNone(r['eventDate']);self.assertEqual(r['stage'],'拟议或计划')
    def test_future_duplicate(self):
        r=run(self.spec([self.item(),self.item(),self.item(id='b',date='2026-10-04')]),'.')
        self.assertEqual(len(r['timeline']),1);self.assertEqual(len(r['excluded']),1)
    def test_conflicting_id(self):
        with self.assertRaises(ValueError):run(self.spec([self.item(),self.item(title='其他')]),'.')
    def test_failure_keeps_timestamp(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'research-data/events/CN/600036/2026-09-03-2026-10-03.json';p.parent.mkdir(parents=True)
            p.write_text(json.dumps({'rows':[self.item()],'sources':['test'],'retrievedAt':'2026-10-01T00:00:00Z'}))
            before=p.read_bytes()
            def fail(*args):raise PermissionError('403')
            r=run({**self.spec(),'refresh':True},folder,fail)
            self.assertEqual(r['collectionStatus'],'cached-after-failure');self.assertEqual(p.read_bytes(),before);self.assertEqual(r['retrievedAt'],'2026-10-01T00:00:00Z')
    def test_hk_requires_input(self):
        r=run({**self.spec(),'market':'HK','code':'00700','refresh':True},'.',lambda *a: (_ for _ in ()).throw(AssertionError()))
        self.assertEqual(r['collectionStatus'],'unsupported')
    def test_monitor_idempotent_and_change(self):
        r=run(self.spec([self.item()]),'.');a=monitor({'result':r})
        self.assertEqual(len(a['alerts']),1);self.assertEqual(monitor({'result':r,'seen':a['seen']})['alerts'],[])
        r['timeline'][0]['title']='修订公告';self.assertEqual(monitor({'result':r,'seen':a['seen']})['alerts'][0]['reason'],'changed')
    def test_news_no_official_upgrade(self):
        r=run(self.spec([self.item(sourceType='news',text='报道声称公司盈利增长')]),'.')
        self.assertEqual(r['timeline'][0]['originalVerification'],'not-verified')
    def test_wrong_subject_not_reassigned(self):
        for change in [{'code':'600519'},{'market':'US'}]:
            with self.assertRaisesRegex(ValueError,'身份'):run(self.spec([self.item(**change)]),'.')
    def test_compact_date_not_silently_excluded(self):
        with self.assertRaisesRegex(ValueError,'YYYY-MM-DD'):run(self.spec([self.item(date='20261003')]),'.')
        with self.assertRaisesRegex(ValueError,'YYYY-MM-DD'):run({**self.spec([]),'asOf':'20261003'},'.')
if __name__=='__main__':unittest.main()
