"""Generate an explicit historical IPO cash scenario from cached facts and calendar."""
import argparse,datetime as dt,json
from decimal import Decimal,ROUND_FLOOR,ROUND_HALF_UP
from pathlib import Path
from cash_repo_ledger import amount,run
from trading_calendar import is_open,next_open

def generate(source,overlays,calendar,capital,start,end):
 opening=amount(capital);lo=dt.date.fromisoformat(start);hi=dt.date.fromisoformat(end)
 if lo.year!=calendar['year'] or hi.year!=calendar['year'] or hi<lo:raise ValueError('Observation range outside supplied calendar')
 if end>source['fetchedAt'][:10]:raise ValueError('Historical scenario cannot extend beyond cached data date')
 if opening<=0:raise ValueError('Positive capital required')
 cash=opening;pending=[];issues=[];excluded=[]
 rows=sorted([r for r in source['records'] if r.get('applyDate') and start<=r['applyDate']<=end],key=lambda r:(r['applyDate'],r['code']))
 for raw in rows:
  r={**raw,**overlays.get('records',{}).get(raw['code'],{})};code=r['code']
  try:
   if any(r.get(k) is None for k in ['price','maxShares','ratePct','gainPct','refundDate','listingDate']):raise ValueError('Required numeric/date fields missing')
   price=amount(r['price']);rate=amount(r['ratePct']);gain=Decimal(str(r['gainPct']));limit=amount(r['maxShares']);minimum=amount(r.get('minShares') or 100)
   if not gain.is_finite() or gain< -100 or price<=0 or not 0<rate<=100 or limit%100 or minimum%100 or minimum<=0 or minimum>limit:raise ValueError('Invalid price/rate/lot/gain inputs')
   if not is_open(r['applyDate'],calendar):raise ValueError('Subscription date outside calendar trading days')
   refund=r['refundDate'] if is_open(r['refundDate'],calendar) else next_open(r['refundDate'],calendar)
   sale=next_open(r['listingDate'],calendar)
   if not r['applyDate']<refund<=sale:raise ValueError('Refund/sale date sequence inconsistent')
   if sale>end:raise ValueError('Sale availability beyond observation window')
   released=[x for x in pending if x[0]<r['applyDate']];cash+=sum((x[1] for x in released),Decimal(0));pending=[x for x in pending if x[0]>=r['applyDate']]
   shares=min((cash/(price*100)).to_integral_value(rounding=ROUND_FLOOR)*100,limit)
   if shares<minimum:raise ValueError('Insufficient available capital after prior freezes')
   allocated=(shares*rate/10000).to_integral_value(rounding=ROUND_FLOOR)*100
   subscribed=(shares*price).quantize(Decimal('.01'),rounding=ROUND_HALF_UP);principal=(allocated*price).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
   proceeds=(principal*(1+gain/100)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
   issue={'id':code,'applyDate':r['applyDate'],'announcedRefundDate':r['refundDate'],'refundAvailableDate':refund,'saleAvailableDate':sale,'subscriptionFunds':str(subscribed),'allocatedPrincipal':str(principal),'saleNetProceeds':str(proceeds),'subscriptionShares':str(shares),'allocatedWholeLotShares':str(allocated),'dateBasis':'Scenario: announced refund rolled to trading day; first-close sale available next BSE trading day, not broker confirmation','numericBasis':{k:'registered-original' if r.get('officialFieldVerification',{}).get(k,{}).get('status')=='original-numeric-matched' else 'third-party-cache' for k in ['price','maxShares','ratePct','gainPct']},'feeAssumption':'zero fees, gross proceeds only'}
   cash-=subscribed;pending.extend([(refund,subscribed-principal),(sale,proceeds)]);issues.append(issue)
  except (ValueError,TypeError,KeyError) as error:excluded.append({'code':code,'reason':str(error)})
 plan={'capital':str(opening),'start':start,'end':end,'issues':issues,'repos':[],'mode':'historical-explicit-date-scenario','sourceFetchedAt':source['fetchedAt'],'calendarSource':calendar.get('sourceUrl'),'accountAvailabilityVerified':False,'limitations':['Same-day subscriptions precede releases','Whole-lot allocations only; odd-lot allocation unknown','First-day closing sale and zero fees assumed; no execution','Actual rates and gains are hindsight, never forecasts']}
 return {'plan':plan,'ledger':run(plan),'excluded':excluded,'sampleCount':len(rows)}
def main():
 p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--overlays',type=Path,required=True);p.add_argument('--calendar',type=Path,required=True);p.add_argument('--capital',required=True);p.add_argument('--start',required=True);p.add_argument('--end',required=True);p.add_argument('--out-dir',type=Path,required=True);a=p.parse_args()
 read=lambda f:json.loads(f.read_text(encoding='utf-8'))
 result=generate(read(a.data),read(a.overlays),read(a.calendar),a.capital,a.start,a.end);a.out_dir.mkdir(parents=True,exist_ok=False)
 for key in ['plan','ledger','excluded']:(a.out_dir/(key+'.json')).write_text(json.dumps(result[key],ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'sampleCount':result['sampleCount'],'participated':len(result['plan']['issues']),'excluded':len(result['excluded']),'feasible':result['ledger']['feasible']}))
if __name__=='__main__':main()
