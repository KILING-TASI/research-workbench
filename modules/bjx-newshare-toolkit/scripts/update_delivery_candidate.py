"""One independent command collects data and builds a reviewable page; never optimizes models."""
import argparse,json,subprocess,sys,shutil
from pathlib import Path
from delivery_preflight import inspect as inspect_resources

def inspect_outputs(directory):
 gaps=[];summary={}
 def read(name):
  path=directory/name
  if not path.exists():return None
  try:
   value=json.loads(path.read_text(encoding='utf-8-sig'))
   if not isinstance(value,dict):raise ValueError('候选记录须为对象')
   return value
  except (OSError,UnicodeError,ValueError) as error:
   gaps.append({'stage':'invalid-artifact','path':name,'reason':str(error)});return None
 data=read('data.json')
 if data:
  announcement=data.get('announcementRefresh',{});summary['announcementRefresh']=announcement
  if announcement.get('failed',0):gaps.append({'stage':'announcements','failed':announcement['failed']})
  if announcement.get('pending',0):gaps.append({'stage':'announcements-pending','pending':announcement['pending'],'reason':'Bounded batch left objects unqueried; this is not a completed refresh'})
 download=read('originals/manifest.json')
 if download:
  summary['downloaded']=len(download.get('documents',[]))
  for item in download.get('details',[]):
   if item.get('status')!='downloaded':gaps.append({'stage':'download',**item})
  for item in download.get('missing',[]):gaps.append({'stage':'original-link',**item})
 extract=read('original-candidates.json')
 if extract:
  summary['extractedDocuments']=len(extract.get('documents',[]))
  if not extract.get('documents'):gaps.append({'stage':'extraction','reason':'No documents available for extraction'})
  for item in extract.get('documents',[]):
   if item.get('status')!='extracted-for-review':gaps.append({'stage':'extraction',**item});continue
   if item.get('ocrReviewRequired'):gaps.append({'stage':'ocr-review','code':item.get('code'),'reason':'External OCR candidates require page image review; no automatic numeric approval'})
   for field,result in item.get('fields',{}).items():
    if result.get('status')!='unique-candidate':gaps.append({'stage':'field','code':item.get('code'),'field':field,**result})
 diff=read('data-diff.json')
 if diff:
  summary['dataRequiresReview']=diff.get('requiresReview');summary['originalConflictCount']=len(diff.get('originalConflicts',[]));summary['resolvedOriginalDifferenceCount']=len(diff.get('resolvedOriginalDifferences',[]))
  for conflict in diff.get('originalConflicts',[]):gaps.append({'stage':'original-conflict',**conflict})
 return summary,gaps

def main():
 p=argparse.ArgumentParser();p.add_argument('--out-dir',type=Path,required=True);p.add_argument('--announcement-limit',type=int,default=20);p.add_argument('--pdf-manifest',type=Path);p.add_argument('--original-limit',type=int,default=8)
 p.add_argument('--previous',type=Path);p.add_argument('--overlays',type=Path);p.add_argument('--template',type=Path);p.add_argument('--model',type=Path);p.add_argument('--bse-calendar',type=Path)
 a=p.parse_args()
 if not 0<=a.announcement_limit<=50 or not 0<=a.original_limit<=50:raise ValueError('Limits must be 0..50')
 if a.out_dir.exists():raise ValueError('Use a new output directory')
 root=Path(__file__).resolve().parents[1];a.out_dir.mkdir(parents=True)
 report={'mode':'review-candidate','modelOptimizationRun':False,'liveFilesOverwritten':False,'steps':[]}
 report['requestedCoverage']={'issuanceRefresh':True,'announcementMetadata':a.announcement_limit>0,'originalDownload':not a.pdf_manifest and a.original_limit>0,'originalExtraction':bool(a.pdf_manifest or a.original_limit),'historicalModelReference':a.model is not None,'note':'Requested steps are not completion or original verification; inspect steps, gaps and originalEvidenceApproved.'}
 previous=a.previous or root/'assets/data.json'
 overlays=a.overlays or root/'assets/calendar-verified-fields.json'
 template=a.template or (root/'assets/bjx-panel.template.html' if (root/'assets/bjx-panel.template.html').is_file() else root/'assets/bjx-panel.html')
 overrides={'assets/data.json':previous,'assets/calendar-verified-fields.json':overlays,'assets/bjx-panel.html':template}
 preflight=inspect_resources(root,'update',overrides)
 for name,path in [('model',a.model),('bse-calendar',a.bse_calendar),('pdf-manifest',a.pdf_manifest)]:
  if path is not None and not path.is_file():preflight['missingResources'].append(str(path))
 report['resourceCheck']=preflight
 if preflight['missingResources']:
  report.update(status='missing-project-resources',summary={},gaps=[{'stage':'resources','path':name} for name in preflight['missingResources']],originalEvidenceApproved=False)
  (a.out_dir/'update-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
  print(json.dumps({'status':report['status'],'missingResources':preflight['missingResources'],'out':str(a.out_dir)},ensure_ascii=False))
  raise SystemExit(2)
 build=['build_bjx_workbench.py','--data',str(a.out_dir/'data.json'),'--overlays',str(overlays),'--template',str(template),'--out',str(a.out_dir/'bjx-panel.html')]
 if a.model:build+=['--model',str(a.model)]
 if a.bse_calendar:build+=['--bse-calendar',str(a.bse_calendar)]
 commands=[['refresh_public_data.py','--previous',str(previous),'--out',str(a.out_dir/'data.json'),'--announcement-limit',str(a.announcement_limit)],build]
 commands.append(['compare_delivery_data.py','--previous',str(previous),'--candidate',str(a.out_dir/'data.json'),'--overlays',str(overlays),'--out',str(a.out_dir/'data-diff.json')])
 if a.pdf_manifest:commands.append(['extract_issuance_evidence.py','--manifest',str(a.pdf_manifest),'--out',str(a.out_dir/'original-candidates.json')])
 if not a.pdf_manifest and a.original_limit:
  commands.append(['download_issuance_originals.py','--data',str(a.out_dir/'data.json'),'--out-dir',str(a.out_dir/'originals'),'--limit',str(a.original_limit)])
  commands.append(['extract_issuance_evidence.py','--manifest',str(a.out_dir/'originals/manifest.json'),'--out',str(a.out_dir/'original-candidates.json')])
 for args in commands:
  try:
   r=subprocess.run([sys.executable,str(root/'scripts'/args[0]),*args[1:]],capture_output=True,text=True,encoding='utf-8',timeout=300)
  except (subprocess.TimeoutExpired,OSError) as error:
   report['steps'].append({'script':args[0],'exitCode':None,'stdout':'','stderr':str(error),'status':'timeout' if isinstance(error,subprocess.TimeoutExpired) else 'launch-failed'});break
  report['steps'].append({'script':args[0],'exitCode':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
  if r.returncode:break
 report['status']='ready-for-review' if len(report['steps'])==len(commands) and all(s['exitCode']==0 for s in report['steps']) else 'failed-old-delivery-retained'
 if report['status']=='ready-for-review':
  for name in ['workbench.html','workbench-shell.css','workbench-shell.js','workbench-theme.css','bjx-workbench.css','bjx-workbench.js','cash-ledger.js','cash-plan.js','cash-repo-plan.js','cash-plan-example.json']:
   shutil.copy2(root/'assets'/name,a.out_dir/name)
 report['summary'],report['gaps']=inspect_outputs(a.out_dir)
 if report['status']=='ready-for-review' and report['gaps']:report['status']='candidate-with-gaps'
 report['originalEvidenceApproved']=False
 (a.out_dir/'update-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'status':report['status'],'out':str(a.out_dir)},ensure_ascii=False))
 if report['status']=='failed-old-delivery-retained':raise SystemExit(1)
if __name__=='__main__':main()
