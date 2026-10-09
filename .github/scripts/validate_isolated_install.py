"""Single-repository exported-source/venv smoke; no author caches or specialist repos."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

repo = Path(__file__).resolve().parents[2]
root = Path(tempfile.mkdtemp(prefix='single-repo-install-'))
source = root / 'source'; source.mkdir()
archive = root / 'source.zip'
subprocess.run(['git', 'archive', '--format=zip', '-o', str(archive), 'HEAD'], cwd=repo, check=True)
with zipfile.ZipFile(archive) as data: data.extractall(source)
home = root / 'empty-user'; home.mkdir()
env = {k: v for k, v in os.environ.items() if not k.startswith(('PYTHON', 'RESEARCH_WORKBENCH_', 'PORTFOLIO_', 'CODEX'))}
env.update(HOME=str(home), USERPROFILE=str(home), APPDATA=str(home/'appdata'), LOCALAPPDATA=str(home/'local'), XDG_CACHE_HOME=str(home/'cache'), PIP_CACHE_DIR=str(home/'pip-cache'))
subprocess.run([sys.executable, '-m', 'venv', str(root/'venv')], env=env, check=True)
python = root/'venv'/('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
work = root/'run'; work.mkdir()
record = {'scope': 'isolated export/process/venv; not new OS', 'commands': [], 'archiveSha256': hashlib.sha256(archive.read_bytes()).hexdigest()}
def run(args, cwd=work, success=True, executable=python):
    command = [str(executable), '-X', 'utf8', *map(str, args)]
    p = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, encoding='utf-8')
    record['commands'].append({'args':command,'cwd':str(cwd),'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
    assert (p.returncode == 0) == success, record['commands'][-1]
    return p
module = 'cnlookthrough' if (source/'cnlookthrough').is_dir() else 'cnreconcile' if (source/'cnreconcile').is_dir() else None
if module:
    wheels = root/'wheels'; wheels.mkdir()
    run(['-m','pip','wheel',source,'--no-deps','--wheel-dir',wheels], executable=Path(sys.executable))
    wheel = next(wheels.glob('*.whl')); record['wheelSha256']=hashlib.sha256(wheel.read_bytes()).hexdigest()
    with zipfile.ZipFile(wheel) as data:
        record['licenses']=[n for n in data.namelist() if n.endswith(('/LICENSE','/THIRD_PARTY_NOTICES.md'))]
        assert len(record['licenses']) == 2
    run(['-m','pip','install','--no-index','--no-deps',wheel])
    sample=work/'demo.json';sample.write_bytes((source/'examples/demo.json').read_bytes())
    cmd=['-I','-m',module,sample,'--format','html','--out',work/'report.html']
    run(cmd); before=hashlib.sha256((work/'report.html').read_bytes()).hexdigest()
    run(cmd,success=False);assert hashlib.sha256((work/'report.html').read_bytes()).hexdigest()==before
    run(['-I','-m',module,sample,'--out',work/'result.json'])
    result=json.loads((work/'result.json').read_text('utf-8'))
    if module=='cnlookthrough':
        assert abs(result['knownExposure']-.84)<1e-12 and abs(result['unknownExposure']-.16)<1e-12
    else:
        assert result['results'][0]['difference']=='0.00' and result['results'][1]['difference']=='-20000000.00'
        assert result['results'][0]['pageEvidenceStatus']=='declared-not-page-verified'
    assert '教学' in (work/'report.html').read_text('utf-8')
    probe=f"import {module},sys,json,importlib.util;print(json.dumps({{'origin':{module}.__file__,'sysPath':sys.path,'pdf':bool(importlib.util.find_spec('pdfplumber'))}}))"
    state=json.loads(run(['-I','-c',probe]).stdout);assert Path(state['origin']).is_relative_to(root/'venv') and not state['pdf']
    record.update(environment=state,result=result,status='independent teaching report passed; optional PDF not installed')
else:
    cmd=['-E','-s',source/'scripts/start.py','demo','--out-dir',work/'report']
    run(cmd,cwd=source);run(cmd,cwd=source,success=False)
    assert '教学' in (work/'report/基金比较说明.html').read_text('utf-8')
    probe="import sys,json;sys.path.insert(0,'scripts');import specialist_loader;out={};\nfor d in specialist_loader.DOMAINS:\n try:specialist_loader.location(d);out[d]='unexpected found'\n except ValueError as e:out[d]=str(e)\nprint(json.dumps({'origin':specialist_loader.__file__,'sysPath':sys.path,'specialists':out}))"
    state=json.loads(run(['-E','-s','-c',probe],cwd=source).stdout)
    assert Path(state['origin']).is_relative_to(source) and all('独立工具不可用' in v for v in state['specialists'].values())
    record.update(environment=state,status='partial: standalone teaching passed; migrated paths require absent specialist packages')
record['visual']='not tested';record['publishedRelease']='not tested'
(root/'receipt.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(record,ensure_ascii=False))
