import unittest
from unittest.mock import patch
import market_collect as m
class HistoryDateTests(unittest.TestCase):
 def test_primary_history_requires_canonical_calendar_date(self):
  for date in ['20260901','2026-W36-2','2026-9-1','2026-02-30']:
   payload={'data':{'code':'510880','name':'红利ETF','klines':[date+',1,1,1,1,0,0']}}
   with self.subTest(date=date),patch.object(m,'fetch',return_value=payload),self.assertRaises(ValueError):
    m.eastmoney_history('510880','1','2026-01-01','2026-09-30')
  payload={'data':{'code':'510880','name':'红利ETF','klines':['2026-09-01,1,1,1,1,0,0']}}
  with patch.object(m,'fetch',return_value=payload):self.assertEqual(m.eastmoney_history('510880','1','2026-01-01','2026-09-30')[0][0]['date'],'2026-09-01')
 def test_fallback_does_not_silently_normalize_noncanonical_date(self):
  for date in ['20260901','2026-W36-2','2026-02-30']:
   payload={'code':0,'data':{'sh510880':{'qt':{'sh510880':['','红利ETF','510880']},'day':[[date,'1','1','1','1','0']]}}}
   with self.subTest(date=date),patch.object(m,'eastmoney_history',side_effect=ValueError('primary unavailable')),patch.object(m,'fetch',return_value=payload),self.assertRaises(ValueError):
    m.history('510880','1','2026-01-01','2026-09-30')

class FinancialDisclosureDateTests(unittest.TestCase):
 def test_invalid_period_or_publication_is_not_accepted(self):
  for period,published in [('20260630','2026-08-27'),('2026-06-30','20260827'),('2026-06-30','2026-06-29'),('2026-02-30','2026-08-27')]:
   payload={'result':{'pages':1,'data':[{'SECURITY_CODE':'600406','REPORT_DATE':period,'NOTICE_DATE':published}]}}
   with self.subTest(period=period,published=published),patch.object(m,'fetch',return_value=payload),self.assertRaises(ValueError):m.financials('600406','2026-01-01','2026-09-30')
 def test_cutoff_excludes_not_yet_disclosed_period(self):
  payload={'result':{'pages':1,'data':[{'SECURITY_CODE':'600406','REPORT_DATE':'2026-06-30 00:00:00','NOTICE_DATE':'2026-08-27 00:00:00'},{'SECURITY_CODE':'600406','REPORT_DATE':'2026-09-30 00:00:00','NOTICE_DATE':'2026-10-27 00:00:00'}]}}
  with patch.object(m,'fetch',return_value=payload):
   rows,sources=m.financials('600406','2026-01-01','2026-09-30')
   self.assertEqual([r['period'] for r in rows],['2026-06-30']);self.assertEqual(rows[0]['publishedAt'],'2026-08-27')

class FinancialPageCountTests(unittest.TestCase):
 def test_invalid_page_count_is_not_truncated_into_success(self):
  row={'SECURITY_CODE':'600406','REPORT_DATE':'2026-06-30','NOTICE_DATE':'2026-08-27'}
  for count in [True,0,-1,1.5,'1',None,101]:
   with self.subTest(count=count),patch.object(m,'fetch',return_value={'result':{'pages':count,'data':[row]}}),self.assertRaisesRegex(ValueError,'分页数量'):m.financials('600406','2026-01-01','2026-09-30')
 def test_changing_page_count_cannot_form_consistent_snapshot(self):
  row={'SECURITY_CODE':'600406','REPORT_DATE':'2026-06-30','NOTICE_DATE':'2026-08-27'}
  with patch.object(m,'fetch',side_effect=[{'result':{'pages':2,'data':[row]}},{'result':{'pages':1,'data':[row]}}]),self.assertRaisesRegex(ValueError,'总数变化'):m.financials('600406','2026-01-01','2026-09-30')

class MarketJSONTests(unittest.TestCase):
 def test_overflow_response_never_returns_infinite_number(self):
  for value in ['1e999','-1e999','NaN','Infinity']:
   with self.subTest(value=value),patch.object(m,'get',return_value='{"value":'+value+'}'),self.assertRaises(ValueError):m.fetch('https://example.com/test')
  with patch.object(m,'get',return_value='{"value":1.23}'):
   self.assertEqual(m.fetch('https://example.com/test'),{'value':1.23})

class HistoryMarketIdentityTests(unittest.TestCase):
 def test_matching_code_does_not_override_wrong_market(self):
  for marker in [0,'0',True,None,1.0]:
   payload={'data':{'code':'510880','market':marker,'name':'红利ETF','klines':['2026-09-01,1,1,1,1,0,0']}}
   with self.subTest(marker=marker),patch.object(m,'fetch',return_value=payload),self.assertRaisesRegex(ValueError,'市场标识'):m.eastmoney_history('510880','1','2026-09-01','2026-09-30')
  for marker in [1,'1']:
   payload={'data':{'code':'510880','market':marker,'name':'红利ETF','klines':['2026-09-01,1,1,1,1,0,0']}}
   with patch.object(m,'fetch',return_value=payload):self.assertEqual(len(m.eastmoney_history('510880','1','2026-09-01','2026-09-30')[0]),1)
