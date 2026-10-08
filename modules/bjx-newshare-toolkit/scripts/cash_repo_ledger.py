"""Explicit dated IPO and reverse-repo cash ledger; no implicit calendars or execution."""
import argparse,datetime as dt,json,re
from decimal import Decimal,ROUND_HALF_UP
from pathlib import Path

def amount(v,digits=None):
 if isinstance(v,bool) or (digits is not None and not re.fullmatch(r'\d+(?:\.\d{1,'+str(digits)+r'})?',str(v))):raise ValueError('Amount/rate precision or decimal format invalid')
 d=Decimal(str(v))
 if not d.is_finite() or d<0:raise ValueError('Nonnegative finite amount required')
 return d

def date_input(value):
 if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):raise ValueError('Date must be YYYY-MM-DD')
 return dt.date.fromisoformat(value)

def identity(prefix,value):
 if not isinstance(value,str) or not value.strip():raise ValueError('Event id required')
 return prefix+value

def run(spec):
 start=date_input(spec['start']);end=date_input(spec['end'])
 if end<start or (end-start).days>3660:raise ValueError('Invalid observation range')
 capital=amount(spec['capital'],2);events=[];repos=[];seen=set()
 def add(date,priority,identity,kind,delta):
  date=date_input(date)
  if date<start:raise ValueError('Event before opening balance date')
  events.append((date,priority,identity,kind,delta))
 for issue in spec.get('issues',[]):
  key=identity('ipo:',issue['id'])
  if key in seen:raise ValueError('Duplicate id')
  seen.add(key);apply=date_input(issue['applyDate']);refund=date_input(issue['refundAvailableDate']);sale=date_input(issue['saleAvailableDate'])
  if not apply<refund<=sale:raise ValueError('Invalid IPO date order')
  if issue.get('announcedRefundDate') and refund<date_input(issue['announcedRefundDate']):raise ValueError('Available refund cannot precede announced refund')
  subscribed=amount(issue['subscriptionFunds'],2);allocated=amount(issue['allocatedPrincipal'],2);proceeds=amount(issue['saleNetProceeds'],2)
  if allocated>subscribed:raise ValueError('Allocation exceeds subscription')
  add(issue['applyDate'],0,key,'subscription',-subscribed);add(issue['refundAvailableDate'],2,key,'refund',subscribed-allocated);add(issue['saleAvailableDate'],2,key,'sale',proceeds)
 for order in spec.get('repos',[]):
  key=identity('repo:',order['id'])
  if key in seen:raise ValueError('Duplicate id')
  seen.add(key)
  trade=date_input(order['tradeDate']);first=date_input(order['firstSettlementDate']);maturity=date_input(order['maturitySettlementDate']);available=date_input(order['availableDate'])
  if not trade<=first<maturity or available<trade:raise ValueError('Invalid repo dates')
  if not order.get('dateBasis'):raise ValueError('Explicit date basis required')
  if available<maturity and not order.get('earlyAvailabilityEvidence'):raise ValueError('Early availability requires evidence')
  if order.get('commission') is None:raise ValueError('Explicit commission required, including a declared zero')
  principal=amount(order['principal'],2);rate=amount(order['annualRatePct'],6);fee=amount(order['commission'],2);days=(maturity-first).days
  interest=(principal*rate/100*days/365).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
  if principal+interest<fee:raise ValueError('Fee exceeds proceeds')
  add(order['tradeDate'],1,key,'repo-open',-principal-fee);add(order['availableDate'],2,key,'repo-return',principal+interest)
  repos.append({'id':order['id'],'actualAccrualDays':days,'grossInterest':str(interest),'commission':str(fee),'netInterest':str(interest-fee),'dateBasis':order['dateBasis']})
 events.sort();cash=capital;minimum=cash;steps=[];daily=[];index=0
 for offset in range((end-start).days+1):
  date=start+dt.timedelta(days=offset);opening=cash;daymin=cash
  while index<len(events) and events[index][0]==date:
   _,_,key,kind,delta=events[index];cash+=delta;minimum=min(minimum,cash);daymin=min(daymin,cash);steps.append({'date':date.isoformat(),'id':key,'kind':kind,'delta':str(delta),'balance':str(cash),'conflict':cash<0});index+=1
  daily.append({'date':date.isoformat(),'opening':str(opening),'closing':str(cash),'intradayMinimum':str(daymin)})
 return {'mode':'explicit-date-scenario-not-account-verification','sameDayOrdering':'subscription then repo-open then releases','capital':str(capital),'endCash':str(cash),'minimumCash':str(minimum),'additionalFundsRequired':str(max(Decimal(0),-minimum)),'feasible':minimum>=0,'repos':repos,'steps':steps,'daily':daily,'unsettledEvents':[{'date':e[0].isoformat(),'id':e[2],'kind':e[3],'delta':str(e[4])} for e in events[index:]],'limitations':['Dates are supplied with explicit basis; no holiday or broker availability is invented','Negative cash flags conflict; it does not assume financing or execute orders','Interest only on each declared repo principal over actual settlement-day interval']}

def main():
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if a.out.exists():raise ValueError('New output required')
 result=run(json.loads(a.input.read_text(encoding='utf-8')));a.out.parent.mkdir(parents=True,exist_ok=True)
 with a.out.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
 print(json.dumps({'feasible':result['feasible'],'additionalFundsRequired':result['additionalFundsRequired']}))
if __name__=='__main__':main()
