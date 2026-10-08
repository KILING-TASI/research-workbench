import copy, unittest
from fund_series_tools import distributions, quality, benchmarks, snapshot_diff

def base():
    return {'code':'test','asOf':'2026-01-06','sourceUrl':'https://example.org/nav',
            'eventCoverage':'verified-complete-for-window','events':[],
            'history':[{'date':f'2026-01-0{i}','nav':v} for i,v in enumerate([1,1,1,1],1)]}

class Tests(unittest.TestCase):
    def test_unknown_currency_not_equal_currency(self):
        with self.assertRaisesRegex(ValueError,'明确同币种'):benchmarks({'asOf':'2026-01-01'})
    def test_bad_benchmark_structure(self):
        for specs in [None,[None],[dict(name='',components=[])],[dict(name='b',components=None)]]:
            with self.subTest(specs=specs),self.assertRaises(ValueError):benchmarks(dict(asOf='2026-01-01',currency='CNY',frequency='daily',fund={},benchmarks=specs))
    def test_missing_calendar_blocks_annualized_benchmark_metrics(self):
        ds=['2026-01-01','2026-01-02','2026-01-04','2026-01-05']
        asset=lambda c,values:dict(code=c,currency='CNY',basis='total-return',sourceUrl='https://example.org/'+c,weight=1,history=[dict(date=d,value=v) for d,v in zip(ds,values)])
        spec=dict(asOf='2026-01-05',frequency='daily',currency='CNY',fund=asset('f',[1,1.03,1.02,1.08]),benchmarks=[dict(name='b',rebalance='each-observation',components=[asset('b',[1,1.01,1.04,1.06])])])
        result=benchmarks(spec);row=result['benchmarks'][0]
        self.assertEqual(result['alignment']['calendarCheck']['status'],'calendar-not-provided')
        for key in ('annualTrackingErrorPct','informationRatio','jensenAlphaAnnualizedPp'):self.assertIsNone(row[key])
        self.assertAlmostEqual(row['excessTotalReturnPp'],2)
        self.assertEqual(row['rebalanceCoverage'],'observed-intervals-not-verified-daily')
        self.assertIn('不能认证',row['benchmarkPathLimitation'])

    def test_common_missing_day_blocks_daily_benchmark_metrics(self):
        ds=['2026-01-01','2026-01-02','2026-01-04','2026-01-05']
        asset=lambda c:dict(code=c,currency='CNY',basis='total-return',sourceUrl='https://example.org/'+c,weight=1,history=[dict(date=d,value=1+i*.01) for i,d in enumerate(ds)])
        spec=dict(asOf='2026-01-05',frequency='daily',currency='CNY',fund=asset('f'),benchmarks=[dict(name='b',rebalance='each-observation',components=[asset('b')])],calendar=dict(start='2026-01-01',end='2026-01-05',dates=['2026-01-0'+str(i) for i in range(1,6)],market='teaching',sourceUrl='https://example.org/calendar',applicabilityConfirmed=True),calendarMarket='teaching')
        result=benchmarks(spec);self.assertEqual(result['alignment']['calendarCheck']['missingDates'],['2026-01-03'])
        self.assertIsNone(result['benchmarks'][0]['annualTrackingErrorPct']);self.assertIsNone(result['benchmarks'][0]['informationRatio'])
    def test_event_without_quantity_does_not_mean_no_event(self):
        s=base();s['events']=[dict(date='2026-01-02',sourceUrl='https://example.org/event')]
        with self.assertRaises(ValueError):distributions(s)
    def test_jump_keeps_observation_interval_without_daily_smoothing(self):
        s={'code':'test','asOf':'2025-04-08','sourceUrl':'https://example.org/nav',
           'history':[{'date':'2025-04-03','nav':1},{'date':'2025-04-07','nav':.8},{'date':'2025-04-08','nav':.6}]}
        r=quality(s);first,second=r['findings']
        self.assertEqual(first['previousDate'],'2025-04-03')
        self.assertEqual(first['calendarDayGap'],4)
        self.assertAlmostEqual(first['changePct'],-20)
        self.assertEqual(second['calendarDayGap'],1)
        self.assertIsNone(r['dateCompleteness'])
    def test_cash_and_reinvest(self):
        s=base();s['history'][1]['nav']=.9;s['history'][2]['nav']=.99;s['history'][3]['nav']=1.08
        s['events']=[{'date':'2026-01-02','cashPerOldUnit':.1,'sourceUrl':'https://example.org/div'}]
        r=distributions(s)
        self.assertAlmostEqual(r['series'][1]['reinvestValue'],1)
        self.assertAlmostEqual(r['series'][-1]['reinvestValue'],1.2)
        self.assertAlmostEqual(r['series'][-1]['cashAccountValue'],1.18)
        self.assertNotEqual(r['reinvest']['totalReturnPct'],r['cashDividend']['totalReturnPct'])
    def test_split_and_missing_events(self):
        s=base();s['history'][1:]=[{'date':f'2026-01-0{i}','nav':.5} for i in [2,3,4]]
        s['events']=[{'date':'2026-01-02','newUnitsPerOldUnit':2,'sourceUrl':'https://example.org/split'}]
        self.assertAlmostEqual(distributions(s)['cashDividend']['totalReturnPct'],0)
        s['eventCoverage']='unknown'
        with self.assertRaises(ValueError):distributions(s)
        self.assertIsNone(quality(s)['distributionConsistency'])
    def test_quality_calendar_and_conflict(self):
        s=base();s['flatRunObservations']=3
        s['calendar']={'dates':['2026-01-01','2026-01-02','2026-01-03','2026-01-04','2026-01-05'],
          'start':'2026-01-01','end':'2026-01-05','sourceUrl':'https://example.org/calendar','applicabilityConfirmed':True}
        s['history'][0]['accumulatedNav']=1;s['history'][1]['accumulatedNav']=1.3
        r=quality(s);self.assertEqual(r['dateCompleteness']['dateCoveragePct'],80)
        self.assertEqual(r['findings'][0]['kind'],'flat-run')
        self.assertFalse(r['distributionConsistency']['rows'][1]['consistent'])
        s['calendar']['applicabilityConfirmed']=False
        self.assertIsNone(quality(s)['dateCompleteness']['dateCoveragePct'])
    def test_custom_benchmark_math(self):
        hs=lambda vs:[{'date':f'2026-01-0{i}','value':v} for i,v in enumerate(vs,1)]
        asset=lambda c,v,w:{'code':c,'history':hs(v),'weight':w,'currency':'CNY','basis':'total-return','sourceUrl':'https://example.org/'+c}
        a=asset('a',[1,1.1,1.21,1.331],.7);b=asset('b',[1,.9,.81,.729],.3)
        s={'asOf':'2026-01-04','frequency':'daily','currency':'CNY','fund':asset('f',[1,1.04,1.0816,1.124864],1),
           'benchmarks':[{'name':'custom','rebalance':'each-observation','components':[a,b]}]}
        r=benchmarks(s)['benchmarks'][0];self.assertAlmostEqual(r['excessTotalReturnPp'],0,places=10)
        s['benchmarks'][0]['rebalance']='buy-and-hold';r=benchmarks(s)['benchmarks'][0]
        self.assertAlmostEqual(r['totalReturnPct'],(1.331*.7+.729*.3-1)*100)
        b['weight']=.5
        with self.assertRaises(ValueError):benchmarks(s)
    def test_snapshot_methodology_not_fake_delta(self):
        a={'subjectCodes':['test'],'asOf':'2026-01-01','metrics':{'Sharpe':1,'missing':None},
           'methodology':{'returnBasis':'reinvest','frequency':'daily','window':'rolling-3y','classificationVersion':'v1'}}
        b=copy.deepcopy(a);b['asOf']='2026-01-04';b['metrics']['Sharpe']=2
        self.assertEqual(snapshot_diff({'before':a,'after':b})['metrics'][0]['difference'],1)
        b['methodology']['classificationVersion']='v2'
        self.assertIsNone(snapshot_diff({'before':a,'after':b})['metrics'][0]['difference'])
        for value in [None,' ',True]:
            invalid=copy.deepcopy(b);invalid['methodology']['classificationVersion']=value
            with self.assertRaisesRegex(ValueError,'非空说明'):snapshot_diff({'before':a,'after':invalid})
        invalid=copy.deepcopy(a);invalid['subjectCodes']='test'
        with self.assertRaisesRegex(ValueError,'主体'):snapshot_diff({'before':invalid,'after':b})
    def test_duplicate_dates_rejected(self):
        s=base();s['history'][1]['date']=s['history'][0]['date']
        with self.assertRaises(ValueError):quality(s)

if __name__=='__main__':unittest.main()
