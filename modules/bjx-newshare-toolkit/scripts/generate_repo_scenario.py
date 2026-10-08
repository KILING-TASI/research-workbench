"""Conservative idle-cash repo scheduling scenario; not market execution or broker dates."""
import argparse,copy,datetime as dt,json
from decimal import Decimal,ROUND_FLOOR
from pathlib import Path
from cash_repo_ledger import amount,run
from trading_calendar import is_open,next_open

def schedule(plan,calendar,annual_rate,utilization=80,commission=0,lot_funds=1000):
 if 'repos' in plan and not isinstance(plan['repos'],list):raise ValueError('Repo orders must be a list')
 if plan.get('repos'):raise ValueError('Base plan must not contain repo orders')
 rate=amount(annual_rate);use=amount(utilization);fee=amount(commission);lot=amount(lot_funds)
 if use>100 or lot<=0:raise ValueError('Utilization must be 0..100; positive lot required')
 result=copy.deepcopy(plan);result.setdefault('repos',[]);baseline=run(plan)
 if not baseline['feasible']:raise ValueError('Base cash plan already has funding conflict')
 ledger=baseline;skipped=[];start=dt.date.fromisoformat(plan['start']);end=dt.date.fromisoformat(plan['end'])
 applies=sorted(x['applyDate'] for x in plan.get('issues',[]))
 for offset in range((end-start).days+1):
  date=(start+dt.timedelta(days=offset)).isoformat()
  if not is_open(date,calendar) or not use:continue
  try:first=next_open(date,calendar);maturity=next_open(first,calendar)
  except ValueError:skipped.append({'date':date,'reason':'Calendar coverage insufficient'});continue
  upcoming=next((d for d in applies if d>date),None)
  if maturity>plan['end'] or (upcoming and maturity>=upcoming):continue
  # Never use releases later on this day to fund an earlier repo-open event.
  opening=Decimal(ledger['daily'][offset]['opening']);negative=sum((Decimal(x['delta']) for x in ledger['steps'] if x['date']==date and Decimal(x['delta'])<0),Decimal(0))
  available=opening+negative-fee
  if available<=0:continue
  principal=(available*use/100/lot).to_integral_value(rounding=ROUND_FLOOR)*lot
  if principal<=0:continue
  order={'id':'idle-'+date,'tradeDate':date,'firstSettlementDate':first,'maturitySettlementDate':maturity,'availableDate':maturity,'principal':str(principal),'annualRatePct':str(rate),'commission':str(fee),'dateBasis':'Scenario: first settlement next supplied-calendar trading day, maturity and availability next trading day after first; NOT actual broker terms'}
  result['repos'].append(order);trial=run(result)
  if not trial['feasible']:result['repos'].pop();skipped.append({'date':date,'reason':'Repo causes future cash conflict'});continue
  ledger=trial
 result['repoScenario']={'annualRatePct':str(rate),'utilizationPct':str(use),'commissionPerOrder':str(fee),'lotFunds':str(lot),'calendarSource':calendar.get('sourceUrl'),'accountAvailabilityVerified':False,'tradeTermsVerified':False,'sameDayOrdering':'subscription then repo-open then releases','note':'Fixed settlement scenario, not a verified one-day repo product; rate and lot are explicit assumptions'}
 return {'plan':result,'ledger':ledger,'baselineEndCash':baseline['endCash'],'incrementalEndCash':str(Decimal(ledger['endCash'])-Decimal(baseline['endCash'])),'skipped':skipped}
def main():
 p=argparse.ArgumentParser();p.add_argument('--plan',type=Path,required=True);p.add_argument('--calendar',type=Path,required=True);p.add_argument('--annual-rate',required=True);p.add_argument('--utilization',default='80');p.add_argument('--commission',default='0');p.add_argument('--lot-funds',default='1000');p.add_argument('--out-dir',type=Path,required=True);a=p.parse_args()
 read=lambda path:json.loads(path.read_text(encoding='utf-8'))
 r=schedule(read(a.plan),read(a.calendar),a.annual_rate,a.utilization,a.commission,a.lot_funds);a.out_dir.mkdir(parents=True,exist_ok=False)
 for k in ['plan','ledger','skipped']:(a.out_dir/(k+'.json')).write_text(json.dumps(r[k],ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'repoOrders':len(r['plan']['repos']),'incrementalEndCash':r['incrementalEndCash'],'feasible':r['ledger']['feasible']}))
if __name__=='__main__':main()
