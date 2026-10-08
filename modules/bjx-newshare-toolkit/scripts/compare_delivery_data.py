"""Review data changes with explicit removal, evidence and archive checks."""
import argparse,hashlib,json
from pathlib import Path

FIELDS=['name','applyDate','refundDate','listingDate','price','maxShares','minShares','onlineShares','ratePct','gainPct','firstClose','approxAnnualPct']
def compare(old,new,overlays):
 def index(snapshot):
  rows=snapshot.get('records',[]);result={}
  for r in rows:
   code=r.get('code')
   if not code or code in result:raise ValueError('Missing or duplicate security code')
   result[code]=r
  return result
 a,b=index(old),index(new);changed=[];conflicts=[];research_changes=[];resolved=[]
 for code,r in b.items():
  changes={k:{'before':a.get(code,{}).get(k),'after':r.get(k)} for k in FIELDS if a.get(code,{}).get(k)!=r.get(k)}
  if changes:changed.append({'code':code,'changes':changes})
  research={k:{'before':a.get(code,{}).get(k),'after':r.get(k)} for k in ['announcements','announcementVersionReview','officialFieldVerification','announcementCorrectionReviews'] if a.get(code,{}).get(k)!=r.get(k)}
  if research:research_changes.append({'code':code,'changes':research})
  verified={**r.get('officialFieldVerification',{}),**overlays.get('records',{}).get(code,{}).get('officialFieldVerification',{})}
  for field,e in verified.items():
   if e.get('status')=='original-numeric-matched' and e.get('value')!=r.get(field):
    conflicts.append({'code':code,'field':field,'candidate':r.get(field),'original':e.get('value'),'sourceUrl':e.get('sourceUrl'),'status':'review-required'})
   prior_difference=r.get('sourceConflicts',{}).get(field,{})
   proof=r.get('fieldProvenance',{}).get(field,{})
   if prior_difference.get('status')=='resolved-original-rechecked' and proof.get('verification')=='original-rechecked' and proof.get('sha256')==e.get('sha256') and r.get(field)==e.get('value'):
    resolved.append({'code':code,'field':field,'thirdParty':prior_difference.get('thirdParty'),'canonicalOriginal':r.get(field),'sourceUrl':e.get('sourceUrl'),'sha256':proof['sha256'],'page':proof.get('page'),'status':'raw-difference-retained-original-preferred'})
 removed=sorted(a.keys()-b.keys());added=sorted(b.keys()-a.keys());archive=old.get('predictionArchive',[])==new.get('predictionArchive',[])
 return {'added':added,'removed':removed,'changed':changed,'researchChanges':research_changes,'originalConflicts':conflicts,'resolvedOriginalDifferences':resolved,'predictionArchivePreserved':archive,'modelOptimizationRun':new.get('modelOptimizationRun',False),'requiresReview':bool(added or removed or changed or research_changes or conflicts or not archive),'notice':'Added securities, numerical and research-source changes require review; matching links do not certify original figures or publication timing'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--previous',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--overlays',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if a.out.exists():raise ValueError('Use a new report filename')
 read=lambda p:json.loads(p.read_text(encoding='utf-8'))
 result=compare(read(a.previous),read(a.candidate),read(a.overlays));result['inputs']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [a.previous,a.candidate,a.overlays]}
 for name in ['trading-calendar-2026.json','bse-trading-calendar-2026.json']:
  calendar=a.overlays.parent/name
  if calendar.exists():result['inputs'][str(calendar)]=hashlib.sha256(calendar.read_bytes()).hexdigest()
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'requiresReview':result['requiresReview'],'changed':len(result['changed']),'originalConflicts':len(result['originalConflicts'])}))
if __name__=='__main__':main()
