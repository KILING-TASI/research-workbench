"""Publish a reviewed data/page pair with rollback snapshots and hash gates."""
import argparse,hashlib,json,re,shutil
from pathlib import Path
from build_bjx_workbench import payload as expected_payload

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def replace(source,target):
 temp=target.with_name(target.name+'.release-pending');shutil.copyfile(source,temp);temp.replace(target)
def publish(candidate,assets,backup,reviewed_diff_hash):
 diff=candidate/'data-diff.json';data=candidate/'data.json';panel=candidate/'bjx-panel.html'
 if digest(diff)!=reviewed_diff_hash:raise ValueError('Reviewed difference report hash changed')
 report=read(diff)
 if not report.get('predictionArchivePreserved') or report.get('modelOptimizationRun'):raise ValueError('Archive/model preservation gate failed')
 inputs=report.get('inputs',{})
 for path in [data,assets/'data.json',assets/'calendar-verified-fields.json']:
  if digest(path) not in inputs.values():raise ValueError('Data, previous snapshot or overlay differs from reviewed inputs')
 snapshot=read(data)
 if snapshot.get('modelOptimizationRun'):raise ValueError('Model optimization not permitted')
 match=re.search(r'<script id="dataset" type="application/json">(.*?)</script>',panel.read_text(encoding='utf-8'),re.S)
 if not match:raise ValueError('Missing page dataset')
 payload=json.loads(match[1]);raw={r['code']:r for r in snapshot['records']};display={r['code']:r for r in payload['records']}
 if len(raw)!=len(snapshot['records']) or len(display)!=len(payload['records']) or raw.keys()!=display.keys():raise ValueError('Page/data security set mismatch')
 if payload.get('fetchedAt')!=snapshot.get('fetchedAt'):raise ValueError('Page/data freshness mismatch')
 overlays=read(assets/'calendar-verified-fields.json').get('records',{})
 expected_page=expected_payload(snapshot,{'records':overlays},{})
 expected_rows={r['code']:r for r in expected_page['records']}
 for code,r in display.items():
  expected={**raw[code],**overlays.get(code,{})}
  for key in ['price','maxShares','minShares','ratePct','gainPct','applyDate','refundDate','listingDate']:
   if r.get(key)!=expected.get(key):raise ValueError('Page numeric mismatch: '+code+'/'+key)
  for key in ['name','onlineShares','firstClose','approxAnnualPct','issuePE','issuePEEvidence','officialFieldVerification','announcements','resultDates','sourceConflicts','hundredReference','announcementVersionReview','announcementCorrectionReviews']:
   if r.get(key)!=expected_rows[code].get(key):raise ValueError('Page research evidence mismatch: '+code+'/'+key)
 if payload.get('annualRecords')!=expected_page['annualRecords']:raise ValueError('Page annual replay data mismatch')
 for key,name in [('tradingCalendar','trading-calendar-2026.json'),('bseTradingCalendar','bse-trading-calendar-2026.json')]:
  file=assets/name
  if file.exists():
   if digest(file) not in inputs.values():raise ValueError('Calendar absent from reviewed inputs')
   if payload.get(key)!=read(file):raise ValueError('Page calendar mismatch: '+key)
  elif payload.get(key):raise ValueError('Page calendar has no registered asset')
 backup.mkdir(parents=True,exist_ok=False)
 names=['data.json','bjx-panel.html']
 before={name:digest(assets/name) for name in names}
 for name in names:shutil.copy2(assets/name,backup/name)
 manifest={'before':before,'reviewedDiffHash':reviewed_diff_hash,'candidateHashes':{name:digest(candidate/name) for name in names},'status':'prepared','modelOptimizationRun':False}
 (backup/'release.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
 try:
  for name in names:replace(candidate/name,assets/name)
  if any(digest(assets/name)!=manifest['candidateHashes'][name] for name in names):raise ValueError('Published hash mismatch')
 except Exception:
  for name in names:shutil.copyfile(backup/name,assets/name)
  manifest['status']='failed-old-pair-restored';(backup/'release.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');raise
 manifest['status']='published-reviewed-pair';(backup/'release.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');return manifest

def restore(backup,assets):
 manifest=read(backup/'release.json');names=['data.json','bjx-panel.html']
 for name in names:
  if digest(backup/name)!=manifest['before'][name]:raise ValueError('Backup integrity failure')
  if digest(assets/name)!=manifest['candidateHashes'][name]:raise ValueError('Current version changed; refusing stale rollback')
 current={name:(assets/name).read_bytes() for name in names}
 try:
  for name in names:replace(backup/name,assets/name)
 except Exception:
  for name in names:(assets/name).write_bytes(current[name])
  raise
 return {'status':'restored-previous-pair','hashes':{name:digest(assets/name) for name in names}}
def main():
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
 q=sub.add_parser('publish');q.add_argument('--candidate',type=Path,required=True);q.add_argument('--assets',type=Path,required=True);q.add_argument('--backup',type=Path,required=True);q.add_argument('--reviewed-diff-hash',required=True)
 q=sub.add_parser('restore');q.add_argument('--assets',type=Path,required=True);q.add_argument('--backup',type=Path,required=True)
 a=p.parse_args();r=publish(a.candidate,a.assets,a.backup,a.reviewed_diff_hash) if a.command=='publish' else restore(a.backup,a.assets);print(json.dumps(r))
if __name__=='__main__':main()
