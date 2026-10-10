# SPDX-License-Identifier: MIT
"""Read only the requested research framework; reject drift in the compiled index."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def route(task,industry=None,depth='standard'):
    if depth not in ('quick','standard','deep'):raise ValueError('深度须为quick/standard/deep')
    base=ROOT/'references';index=json.loads((base/'research-framework.json').read_text(encoding='utf-8'))
    if index.get('schemaVersion')!='research-framework-route/1':raise ValueError('不支持的框架索引版本')
    selected=next((t for t in index['tasks'] if t['id']==task),None)
    if selected is None:raise ValueError('未知任务类型')
    names=selected['references'][:1] if depth=='quick' else selected['references']
    if depth=='deep' and 'research-depth-standard.md' not in names:names=names+['research-depth-standard.md']
    refs=[]
    for name in names:
        p=(base/name).resolve()
        if not p.is_relative_to(base.resolve()) or not p.is_file():raise ValueError('框架引用路径无效')
        digest=hashlib.sha256(p.read_text(encoding='utf-8').encode('utf-8')).hexdigest()
        if digest!=index['referenceSha256'].get(name):raise ValueError('引用内容变化，需更新机读索引而非沿用旧摘要')
        refs.append({'path':str(p),'textSha256Utf8Lf':digest})
    framework=None
    if industry is not None:
        framework=next((x for x in index['industryFrameworks'] if x['code']==industry),None)
        if framework is None:raise ValueError('未知SW2021一级分类代码，不能按名称猜')
    return {'task':task,'depth':depth,'references':refs,'industry':framework,'entry':selected['entry'],'scope':index['scope']}

def main(argv=None):
    p=argparse.ArgumentParser(description='按任务和行业读取方法，不执行取数或估值')
    p.add_argument('--task',required=True);p.add_argument('--industry');p.add_argument('--depth',default='standard');a=p.parse_args(argv)
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8')
    try:
        print(json.dumps(route(a.task,a.industry,a.depth),ensure_ascii=False,indent=2));return 0
    except (ValueError,OSError) as exc:
        print('未完成：'+str(exc),file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
