"""Synchronize reviewed delivery files and update ZIP without bundling private caches."""
import argparse,shutil,zipfile,json
from pathlib import Path
from pathlib import PurePosixPath
FILES=['references/user-guide.md','references/coverage.md','references/research-boundaries.md','assets/example-panel-input.json','assets/example-panel-output.json','assets/example-rates-input.json','assets/example-rates-output.json','scripts/test_annual_cash_alignment.py','scripts/compare_original_versions.py','scripts/test_original_versions.py','scripts/recheck_correction_notices.py','scripts/test_correction_recheck.py','scripts/announcement_versions.py','scripts/test_announcement_versions.py','scripts/test_calendar_coverage_warning.py','scripts/public_issuance_data.py','scripts/test_public_issuance_data.py','scripts/audit_delivery.py','scripts/generate_repo_scenario.py','scripts/test_repo_scheduling.py','scripts/test_browser_repo_schedule.py','assets/cash-repo-plan.js','assets/cash-plan.js','scripts/test_browser_cash_plan.py','scripts/generate_cash_plan.py','scripts/test_cash_plan_generation.py','scripts/test_bse_calendar.py','assets/bse-trading-calendar-2026.json','scripts/release_workbench_candidate.py','scripts/test_candidate_release.py','scripts/test_update_status.py','scripts/download_issuance_originals.py','scripts/test_original_download.py','assets/data.json','scripts/extract_issuance_evidence.py','scripts/test_evidence_extract.py','scripts/recheck_original_evidence.py','scripts/test_original_recheck.py','scripts/compare_delivery_data.py','scripts/update_delivery_candidate.py','scripts/announcements.py','scripts/test_browser_cash_ledger.py','assets/cash-ledger.js','assets/cash-plan-example.json','assets/trading-calendar-2026.json','scripts/trading_calendar.py','scripts/cash_repo_ledger.py','scripts/test_cash_repo_ledger.py','references/cash-repo-ledger.md','SKILL.md','agents/openai.yaml','scripts/refresh_public_data.py','scripts/build_bjx_workbench.py','scripts/publish_bjx_delivery.py','scripts/test_data_delivery.py','assets/workbench.html','assets/workbench.template.html','assets/bjx-panel.html','assets/bjx-workbench.css','assets/bjx-workbench.js','assets/calendar-verified-fields.json','assets/calendar-pe-evidence.json','references/delivery-backlog.json','references/workbench-delivery.md']
FILES.append('references/third-party-notices.md')

def task_entry(name):
 parts=PurePosixPath(name).parts
 return any(parts[i:i+2]==('research','tasks') for i in range(len(parts)-1))

def inspect_preserved_entries(names):
 for name in names:
  path=PurePosixPath(name);parts=set(path.parts)
  if path.is_absolute() or '..' in parts or '\\' in name or ':' in name:raise ValueError('旧ZIP存在异常路径，不能增量发布')
  if task_entry(name):continue  # These entries are excluded when copying below.
  if name.lower().endswith('.pdf') or parts&{'research-data','cache','__pycache__','.git'} or path.name=='.env':
   raise ValueError('旧ZIP包含PDF附件或缓存/敏感路径，须审查重建后再发布：'+name)

def distribution_bytes(rel,body):
 """The downloadable skill starts without author market caches or archived previews."""
 if rel=='assets/data.json':
  return json.dumps({'fetchedAt':None,'source':'首次安装，尚未获取资料','records':[],'predictionArchive':[],'opinions':[],'refreshDetails':[]},ensure_ascii=False,indent=2).encode('utf-8')
 if rel in ['assets/calendar-verified-fields.json','assets/calendar-pe-evidence.json']:
  original=json.loads(body.decode('utf-8-sig'))
  return json.dumps([] if isinstance(original,list) else {},ensure_ascii=False).encode('utf-8')
 if rel=='assets/bjx-panel.html':
  return '<section><h2>北交所新股研究</h2><p>首次安装尚未载入发行资料，请获取资料后生成研究页面。</p></section>'.encode('utf-8')
 return body

def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--installed',type=Path,required=True);p.add_argument('--zip',type=Path,required=True);a=p.parse_args()
 for rel in FILES:
  if not (a.source/rel).is_file():raise ValueError('Missing '+rel)
 temp=a.zip.with_suffix('.pending.zip')
 with zipfile.ZipFile(a.zip) as old:
  candidates=[n[:-len('SKILL.md')] for n in old.namelist() if n.endswith('SKILL.md')]
  if len(candidates)!=1:raise ValueError('Ambiguous archive root')
  inspect_preserved_entries(old.namelist())
  prefix=candidates[0];replace={prefix+r for r in FILES}
  with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as z:
   for info in old.infolist():
    if info.filename not in replace and not task_entry(info.filename):z.writestr(info,old.read(info.filename))
   for rel in FILES:z.writestr(prefix+rel,distribution_bytes(rel,(a.source/rel).read_bytes()))
 with zipfile.ZipFile(temp) as z:
  if z.testzip():raise ValueError('ZIP integrity failed')
  for rel in FILES:
   if z.read(prefix+rel)!=distribution_bytes(rel,(a.source/rel).read_bytes()):raise ValueError('Mismatch '+rel)
 for rel in FILES:
  dest=a.installed/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(a.source/rel,dest)
 temp.replace(a.zip)
 print(json.dumps({'filesSynced':len(FILES),'zipIntegrity':'passed','privatePdfCacheIncluded':False}))
if __name__=='__main__':main()
