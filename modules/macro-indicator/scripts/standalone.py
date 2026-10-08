"""Create a cache-free macro catalog and optionally fetch official observations."""
import argparse
import json
from pathlib import Path
from refresh import refresh

def main():
    p=argparse.ArgumentParser();p.add_argument('--data-dir',type=Path,required=True);p.add_argument('--refresh',action='store_true');a=p.parse_args()
    a.data_dir.mkdir(parents=True,exist_ok=True);dest=a.data_dir/'data.json'
    if not dest.exists():
        rows=json.loads((Path(__file__).resolve().parents[1]/'assets/catalog.json').read_text(encoding='utf-8'))
        for row in rows:
            row.update(value=None,previous=None,history=[],data_period=None,official_release_date=None,fetched_at=None,missing='首次安装，尚未获取数据',modelEligible=False)
            for k in ['display_value','yoy','previousYoy','last_successful_fetch_at','fetch_error']:row.pop(k,None)
        dest.write_text(json.dumps({'catalogVersion':'four-cycles-v1','indicators':rows,'fetchedAt':None,'errors':{}},ensure_ascii=False,indent=2),encoding='utf-8')
    d=refresh(a.data_dir) if a.refresh else json.loads(dest.read_text(encoding='utf-8'))
    print(json.dumps({'output':str(dest),'indicators':len(d['indicators']),'available':sum(r.get('value') is not None for r in d['indicators']),'refreshAttempted':a.refresh},ensure_ascii=False))
if __name__=='__main__':main()
