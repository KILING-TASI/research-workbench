"""Refresh public issuance records without running model research. Outputs a new snapshot."""
import argparse
import datetime as dt
import json
import hashlib
from pathlib import Path
from public_issuance_data import fetch, normalize
from announcements import enrich

def merge(previous, fresh):
    # Preserve independent research assets and archives outside this refresh scope.
    fresh = {**previous, **fresh}
    old = {r['code']: r for r in previous.get('records', [])}
    for record in fresh['records']:
        prior = old.get(record['code'], {})
        for key in ['announcements','announcementUrl','announcementCheckedAt','announcementStatus','announcementSource','announcementError','officialFieldVerification','announcementCorrectionReviews','supplementalSearchEvidence','issuePE','issuePEBasis','issuePEEvidence']:
            if key in prior:
                record[key] = prior[key]
        verification = record.get('officialFieldVerification', {})
        for key, evidence in verification.items():
            if isinstance(evidence, dict) and evidence.get('value') is not None and key in record and record[key] != evidence['value']:
                record.setdefault('sourceConflicts', {})[key] = {'thirdParty':record[key], 'originalRegistered':evidence['value'], 'status':'needs-review'}
    fresh['predictionArchive'] = previous.get('predictionArchive', [])
    fresh['modelOptimizationRun'] = False
    fresh['refreshScope'] = 'Third-party issuance fields only; announcement original verification unchanged'
    return fresh

def refresh(previous, max_announcements=0, diagnostics=None):
    trace=diagnostics if diagnostics is not None else []
    result=merge(previous,normalize(fetch(diagnostics=trace)))
    result['issuanceRequestTrace']=trace
    if not max_announcements:
        if 'announcementRefresh' in previous:result['previousAnnouncementRefresh']=previous['announcementRefresh']
        result['announcementRefresh']={'queried':0,'failed':0,'notRequested':True,'originalNumericVerificationExecuted':False}
    if max_announcements:
        enrich(result,previous,max_queries=max_announcements)
        result['refreshScope']='Issuance fields and issuer-matched announcement metadata; original numeric verification unchanged'
    result['refreshDetails']=[{'code':r['code'],'issuanceStatus':'success',
        'announcementStatus':r.get('announcementStatus','not_checked'),
        'announcementError':r.get('announcementError'),
        'announcementCheckedAt':r.get('announcementCheckedAt'),
        'originalNumericStatus':'preserved-not-reverified' if r.get('officialFieldVerification') else 'not-verified'} for r in result['records']]
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--previous',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--announcement-limit',type=int,default=20);a=p.parse_args()
    if not 0<=a.announcement_limit<=50:raise ValueError('Announcement limit must be 0..50')
    if a.out.exists():raise ValueError('Use a new output filename; never overwrite the successful snapshot')
    previous=json.loads(a.previous.read_text(encoding='utf-8'))
    diagnostics=[]
    failure_path=a.out.with_name(a.out.stem+'-failure.json')
    if failure_path.exists():raise ValueError('Use a new output filename; prior failure record exists')
    old_sha=hashlib.sha256(a.previous.read_bytes()).hexdigest()
    try:result=refresh(previous,a.announcement_limit,diagnostics)
    except Exception as error:
        failure={'status':'failed','oldSnapshotRetained':hashlib.sha256(a.previous.read_bytes()).hexdigest()==old_sha,'previousSha256':old_sha,'lastSuccess':previous.get('fetchedAt'),'error':str(error),'issuanceRequestTrace':diagnostics,'partialSnapshotPublished':False}
        failure_path.parent.mkdir(parents=True,exist_ok=True)
        with failure_path.open('x',encoding='utf-8') as f:json.dump(failure,f,ensure_ascii=False,indent=2)
        print(json.dumps(failure,ensure_ascii=False));raise SystemExit(1)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps({'status':'collected-for-review','out':str(a.out),'records':len(result['records']),'modelOptimizationRun':False},ensure_ascii=False))
if __name__=='__main__':main()
