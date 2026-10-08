"""Explicitly prefer rechecked registered originals; preserve provider values and differences."""
import argparse
import copy
import json
import datetime as dt
import hashlib
from decimal import Decimal
from pathlib import Path
from recheck_original_evidence import recheck


def reconcile(snapshot, overlays, pdf_dir):
    data=copy.deepcopy(snapshot)
    by_code={}
    for row in data['records']:
        if not row.get('code') or row['code'] in by_code:raise ValueError('Missing or duplicate code')
        by_code[row['code']]=row
    checks=recheck(overlays,Path(pdf_dir))
    checked_at=dt.datetime.now(dt.timezone.utc).isoformat()
    actions=[]
    for check in checks['results']:
        row=by_code.get(check['code'])
        if check['status']!='original-rechecked' or row is None:
            actions.append({'code':check['code'],'field':check['field'],'status':'not-applied','reason':check.get('reason','Issuer absent from snapshot')})
            continue
        field=check['field']
        evidence=overlays['records'][check['code']]['officialFieldVerification'][field]
        value=Decimal(str(evidence['value']))
        if not value.is_finite() or value<0:raise ValueError('Invalid registered value')
        numeric=int(value) if field=='maxShares' and value==value.to_integral_value() else float(value)
        if Decimal(str(numeric))!=value:raise ValueError('Canonical JSON number cannot preserve original precision')
        old=row.setdefault('thirdPartyValues',{}).get(field,row.get(field))
        row['thirdPartyValues'][field]=old
        row[field]=numeric
        row.setdefault('officialFieldVerification',{})[field]=copy.deepcopy(evidence)
        proof={'sha256':check['sha256'],'page':check['page'],'sourceUrl':check.get('sourceUrl'),'verification':'original-rechecked','recheckedAt':checked_at,'publicationTimeCertified':False}
        row.setdefault('fieldProvenance',{})[field]=proof
        different=old is None or Decimal(str(old))!=value
        if different:
            row.setdefault('sourceConflicts',{})[field]={'thirdParty':old,'originalRegistered':numeric,'status':'resolved-original-rechecked','resolution':'canonical-original','rawDifferenceRetained':True,**proof}
        actions.append({'code':check['code'],'field':field,'status':'applied-original-rechecked','thirdParty':old,'canonical':numeric,'differenceRetained':different,**proof})
    report={'actions':actions,'recheck':checks,'applied':sum(x['status']=='applied-original-rechecked' for x in actions),'notApplied':sum(x['status']=='not-applied' for x in actions),'boundary':'Explicit original preference after local PDF recheck; raw provider differences retained; not first-publication or document applicability certification'}
    data['originalReconciliation']=report
    return data,report


def main():
    parser=argparse.ArgumentParser()
    for name in ['data','overlays','pdf-dir','out-dir']:parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    if args.out_dir.exists():raise ValueError('Use a new output directory')
    read=lambda path:json.loads(path.read_text('utf-8'))
    data,report=reconcile(read(args.data),read(args.overlays),args.pdf_dir)
    report['inputs']={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in [args.data,args.overlays]}
    args.out_dir.mkdir(parents=True)
    for name,value in [('data.json',data),('reconciliation.json',report)]:
        with (args.out_dir/name).open('x',encoding='utf-8') as output:json.dump(value,output,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps({'applied':report['applied'],'notApplied':report['notApplied'],'out':str(args.out_dir)}))


if __name__=='__main__':main()
