# SPDX-License-Identifier: MIT
"""Build explicit local platform wrappers, without changing root skills or accounts."""
import argparse, hashlib, json, re
from pathlib import Path


def build(catalog, out):
    out = Path(out)
    if out.exists() or out.is_symlink(): raise ValueError('须使用新目录，不覆盖旧分发包')
    spec = json.loads(Path(catalog).read_text('utf-8'))
    rows = spec['skills']; names = set()
    fields = {'name','version','description','description_zh','description_en','source','examples_zh','examples_en','tags_zh','tags_en'}
    for row in rows:
        if not fields <= set(row): raise ValueError('注册字段不完整')
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', row['name']) or row['name'] in names or row['source'] != row['name']: raise ValueError('名称重复或源目录不符')
        names.add(row['name'])
        if not re.fullmatch(r'\d+\.\d+\.\d+',row['version']): raise ValueError('适配层须纯数字三段版本')
        for key in ('examples_zh','examples_en','tags_zh','tags_en'):
            if not isinstance(row[key],list) or not row[key] or any(not isinstance(x,str) or not x.strip() for x in row[key]): raise ValueError('问法或标签无效')
        if row['repositoryUrl'] != 'https://github.com/KILING-TASI/'+row['name']: raise ValueError('仓库地址不符')
    out.mkdir(parents=True)
    for row in rows:
        folder=out/'skills'/row['name']; folder.mkdir(parents=True)
        text='---\nname: '+row['name']+'\ndescription: '+json.dumps(row['description'],ensure_ascii=False)+'\ndescription_zh: '+json.dumps(row['description_zh'],ensure_ascii=False)+'\ndescription_en: '+json.dumps(row['description_en'])+'\nversion: '+row['version']+'\n---\n\n# '+row['name']+'\n\n'+row['description_zh']+'\n\n这是分发薄层，不包含Python运行时与专业引擎。先按[原仓README]('+row['repositoryUrl']+')安装完整工具，读取该版本SKILL与资料说明，再调用已安装入口。缺工具时说明安装条件，不自动下载、安装或复制算法。\n\n示例问法：'+row['examples_zh'][0]+'\n\n计算完成、数据取得与原文核验分别说明；未知不补零，历史结果另存。不得执行交易；适配层MIT不授予第三方资料再分发权。\n'
        (folder/'SKILL.md').write_text(text,'utf-8')
    registry=out/'.codebuddy-skill';registry.mkdir()
    (registry/'marketplace.json').write_text(json.dumps({'name':'kiling-tasi-research-tools','description':'十二个可独立使用的投研工具分发薄层；未在第三方市场上架','skills':[{key:row[key] for key in sorted(fields)} for row in rows]},ensure_ascii=False,indent=2),'utf-8')
    (out/'README.md').write_text('本地分发适配包。格式检查不是目标平台导入验收。适配层版本与专业包版本分开，不提供托管API、自动安装或交易。\n','utf-8')
    (out/'LICENSE').write_text((Path(__file__).parents[1]/'LICENSE').read_text('utf-8'),'utf-8')
    files={str(p.relative_to(out)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file()}
    (out/'receipt.json').write_text(json.dumps({'files':files,'catalogSha256':hashlib.sha256(Path(catalog).read_bytes()).hexdigest(),'platformImportVerified':False},indent=2),'utf-8')
    return len(rows)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--catalog',type=Path,required=True);parser.add_argument('--out-dir',type=Path,required=True);args=parser.parse_args()
    try: print('已生成本地分发薄层：'+str(build(args.catalog,args.out_dir))+'项；平台导入尚未验收。');return 0
    except (ValueError,KeyError,TypeError,OSError) as error:parser.exit(2,'未完成：'+str(error)+'\n')


if __name__=='__main__': raise SystemExit(main())
