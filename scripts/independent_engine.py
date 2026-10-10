"""Explicit optional engines in isolated processes; no downloading or installation."""
import argparse,os,subprocess,sys,json,hashlib,tempfile,shutil
from datetime import datetime,timezone
from pathlib import Path
from collection_validation import unique_pairs,reject_constant,finite_json_float

ENGINES={'lookthrough':'cnlookthrough','financial':'cnreconcile'}


def contract(engine):
    registry=load(Path(__file__).resolve().parents[1]/'references/engine-contracts.json')
    rows=[row for row in registry['engines'] if row.get('id')==engine]
    if len(rows)!=1 or not rows[0].get('bridgeAvailable') or rows[0].get('module')!=ENGINES.get(engine):raise ValueError('引擎尚未有等价可调用契约，不自动启用')
    return dict(rows[0],registryVersion=registry['registryVersion'])


def run(engine,project_dir,input_path,output,format='markdown',timeout=60):
    if engine not in ENGINES or format not in ('json','markdown','html'):raise ValueError('独立引擎或输出格式无效')
    if isinstance(timeout,bool) or not isinstance(timeout,int) or not 1<=timeout<=600:raise ValueError('超时须为1至600秒')
    root=Path(project_dir).resolve();source=Path(input_path).resolve();out=Path(output).absolute()
    module=ENGINES[engine];entry=root/module/'__main__.py'
    if not root.is_dir() or not entry.is_file() or not entry.resolve().is_relative_to(root):raise ValueError('请指定已安装且可信的独立项目目录；不会自动下载')
    if not source.is_file() or source.stat().st_size>16*1024*1024:raise ValueError('输入缺失或超过16MB')
    if out.exists() or out.resolve()==source:raise ValueError('使用新输出文件，不覆盖输入或旧报告')
    declared=load(source)
    definition=contract(engine)
    if isinstance(declared,dict) and declared.get('inputSchema') not in (None,definition['inputSchema']):raise ValueError('输入schema与所选引擎契约不同，未执行')
    env=dict(os.environ,PYTHONIOENCODING='utf-8');env.pop('PYTHONPATH',None)
    try:result=subprocess.run([sys.executable,'-m',module,str(source),'--format',format,'--out',str(out)],cwd=root,env=env,capture_output=True,text=True,encoding='utf-8',timeout=timeout)
    except (subprocess.TimeoutExpired,OSError) as error:raise ValueError('独立工具超时或无法启动，未认证输出成功') from error
    if result.returncode!=0:raise ValueError('独立工具未完成：'+result.stderr.strip()[-2000:])
    if not out.is_file():raise ValueError('工具未留下预期报告，不视为成功')
    return {'engine':engine,'output':str(out),'status':'generated-not-reverified','inputSchema':'independent-not-main-skill-schema','engineContract':definition}


def method_files(engine,project_dir):
    root=Path(project_dir).resolve();folder=root/ENGINES[engine]
    paths=list(folder.glob('*.py'))+[root/'pyproject.toml']
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file() and p.resolve().is_relative_to(root)}


def load(path):
    path=Path(path)
    if not path.is_file() or path.is_symlink() or path.stat().st_size>16*1024*1024:raise ValueError('输入路径或大小异常')
    return json.loads(path.read_text('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)


def bundle(engine,project_dir,output_dir,input_path=None,continue_from=None,timeout=60):
    if engine not in ENGINES:raise ValueError('独立引擎无效')
    if bool(input_path)==bool(continue_from):raise ValueError('新输入或旧报告二选一')
    destination=Path(output_dir).absolute()
    if destination.exists():raise ValueError('另建结果目录，不覆盖旧报告')
    note='本次按提供的资料计算，没有更新行情或公告。'
    if continue_from:
        previous=Path(continue_from).resolve();request=load(previous/'research-request.json');manifest=load(previous/'report-manifest.json')
        if manifest.get('files',{}).get('research-request.json')!=hashlib.sha256((previous/'research-request.json').read_bytes()).hexdigest():raise ValueError('旧请求记录已改动，需重新确认输入接口')
        if request.get('engine')!=engine:raise ValueError('旧报告引擎不同，不能混用输入')
        source=previous/'input.json'
        if source.is_symlink() or source.resolve().parent!=previous:raise ValueError('旧输入路径越界')
        if manifest.get('files',{}).get('input.json')!=hashlib.sha256(source.read_bytes()).hexdigest():raise ValueError('旧输入已改动，需明确提供新输入')
        note='沿用旧输入重新计算，未联网更新；不是数据已刷新。'
        if manifest.get('methodFiles')!=method_files(engine,project_dir):note+=' 计算方法与旧版有变化，结果差别不能直接解释成市场变化。'
    else:source=Path(input_path).resolve()
    spec=load(source)
    definition=contract(engine)
    if not isinstance(spec,dict):raise ValueError('独立接口输入须为对象')
    before=method_files(engine,project_dir)
    from research_brief_html import render
    with tempfile.TemporaryDirectory(prefix='independent-report-') as temporary:
        stage=Path(temporary)/'bundle';stage.mkdir();shutil.copyfile(source,stage/'input.json')
        run(engine,project_dir,stage/'input.json',stage/'result.json','json',timeout)
        result=load(stage/'result.json')
        run(engine,project_dir,stage/'input.json',stage/'研究结果.md','markdown',timeout)
        if before!=method_files(engine,project_dir):raise ValueError('生成期间工具代码发生变化，未发布不一致报告')
        body=(stage/'研究结果.md').read_text('utf-8')+'\n\n'+note+' 如果原文PDF或读取软件有变化，相关结果仍需重新核对。\n'
        lines=body.splitlines()
        first=next((i for i,line in enumerate(lines) if line.strip() and not line.lstrip().startswith('#')),None)
        if first is not None and not lines[first].startswith('> '):lines[first]='> '+lines[first]
        body='\n'.join(lines)+'\n'
        (stage/'研究结果.md').write_text(body,'utf-8');(stage/'研究结果.html').write_text(render(body,'独立工具研究结果'),'utf-8')
        (stage/'engine-contract.json').write_text(json.dumps({'engineContract':definition,'toolVersion':result.get('toolVersion','legacy-unregistered'),'rulesVersion':result.get('rulesVersion','legacy-unregistered'),'inputSchema':result.get('inputSchema',definition['inputSchema'])},ensure_ascii=False,indent=2),'utf-8')
        names=[]
        if engine=='lookthrough':names=[r['id'] for r in spec.get('positions',[]) if isinstance(r,dict) and isinstance(r.get('id'),str)]
        else:names=list(dict.fromkeys(r.get('reported',{}).get('entity') for r in spec.get('pairs',[]) if isinstance(r,dict) and isinstance(r.get('reported',{}).get('entity'),str)))
        request={'command':'independent','engine':engine,'names':names,'asOf':spec.get('asOf'),'schema':'independent'}
        (stage/'research-request.json').write_text(json.dumps(request,ensure_ascii=False,indent=2),'utf-8')
        files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.iterdir() if p.is_file()}
        manifest={'files':files,'primaryReport':'研究结果.html','savedAt':datetime.now(timezone.utc).isoformat(),'methodFiles':before,'inputSchema':'independent'}
        (stage/'report-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf-8')
        destination.parent.mkdir(parents=True,exist_ok=True);destination.mkdir()
        for p in stage.iterdir():shutil.copyfile(p,destination/p.name)
    return {'status':'generated-not-reverified','directory':str(destination),'engine':engine}


if __name__=='__main__':
    p=argparse.ArgumentParser(description='调用明确安装的独立工具，不替换主包计算或自动安装')
    p.add_argument('engine',choices=ENGINES);p.add_argument('--project-dir',required=True)
    source=p.add_mutually_exclusive_group(required=True);source.add_argument('--input');source.add_argument('--continue-from')
    target=p.add_mutually_exclusive_group(required=True);target.add_argument('--out');target.add_argument('--out-dir')
    p.add_argument('--format',choices=['json','markdown','html'],default='markdown');p.add_argument('--timeout',type=int,default=60)
    a=p.parse_args()
    try:
        if a.out_dir:
            r=bundle(a.engine,a.project_dir,a.out_dir,a.input,a.continue_from,a.timeout);print('报告已保存，可按持仓或公司名称找回：'+r['directory']+'；资料未自动更新。')
        else:
            if a.continue_from:raise ValueError('接续报告请使用--out-dir新目录')
            r=run(a.engine,a.project_dir,a.input,a.out,a.format,a.timeout);print('报告已生成：'+r['output']+'；独立接口，生成不代表资料已核验。')
    except ValueError as error:p.exit(2,str(error)+'\n')
