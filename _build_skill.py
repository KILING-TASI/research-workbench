"""Build only declared public Skill resources into a relocatable wheel."""
from pathlib import Path
from shutil import copyfile
from setuptools.command.build_py import build_py

PACKAGE = 'research_workbench'
ROOTS = ['examples/disclosure-teaching.json', 'README.en.md', 'CHANGELOG.md', 'NAV_IMPLEMENTATION.json', 'AUDIT_SCOPE.md', 'EXPANSION_RELEASE.md', 'FORMAT_SCOPE.md', 'EXPANSION.md', 'examples/expansion-teaching', 'BEGINNER.md', 'try_demo.py', 'Start-Demo.cmd', 'Start-Demo.sh', 'README.md', 'SKILL.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md', 'DISCLAIMER.md', 'scripts', 'references', 'agents', 'modules']
EXCLUDED = []
EXTENSIONS = {'.cmd', '.sh', '.py','.js','.cjs','.mjs','.md','.json','.txt','.csv','.html','.css','.yaml','.yml','.jpg','.png','.svg'}

class BuildSkill(build_py):
    def run(self):
        super().run()
        root = Path(__file__).resolve().parent
        dest = Path(self.build_lib) / PACKAGE / '_skill'
        for name in ROOTS:
            entry = root / name
            files = entry.rglob('*') if entry.is_dir() else [entry]
            for path in files:
                rel = path.relative_to(root)
                if not path.is_file() or '__pycache__' in rel.parts or rel.as_posix() in EXCLUDED:
                    continue
                if not path.name.upper().startswith(('LICENSE','NOTICE','COPYING','COPYRIGHT')) and path.suffix.lower() not in EXTENSIONS:
                    continue
                if not path.resolve().is_relative_to(root):
                    raise ValueError('资源指向源码目录外')
                target = dest / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                copyfile(path, target)
        for required in ['README.md','LICENSE','THIRD_PARTY_NOTICES.md','SKILL.md']:
            if not (dest / required).is_file():
                raise ValueError('缺少完整 Skill/许可资源：' + required)
