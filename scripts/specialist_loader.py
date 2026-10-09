"""Thin trusted-library selection. No discovery, downloads, installs or algorithm fallback."""
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import types

DOMAINS = {
    'lookthrough': ('cnlookthrough', 'RESEARCH_WORKBENCH_LOOKTHROUGH_DIR'),
    'financial': ('cnreconcile', 'RESEARCH_WORKBENCH_FINANCIAL_DIR'),
    'portfolio': ('portfolio_engine', 'RESEARCH_WORKBENCH_PORTFOLIO_DIR'),
}
LAST_PROVENANCE = {}


def location(domain, project_dir=None):
    package, variable = DOMAINS[domain]
    declared = project_dir or os.environ.get(variable)
    if declared:
        root = Path(declared).resolve()
        folder = root / ('src/' + package if domain == 'portfolio' else package)
    else:
        installed = importlib.util.find_spec(package)
        folder = Path(installed.origin).resolve().parent if installed and installed.origin else None
    if folder is None or not folder.is_dir() or not (folder / '__init__.py').is_file():
        raise ValueError('独立工具不可用：请安装对应专业包，或明确设置' + variable + '为可信项目目录；不会自动下载安装或回到重复算法')
    return folder.resolve()


def fingerprint(folder):
    result = {}
    for path in sorted(folder.glob('*.py')):
        if path.is_file():
            with open(path, 'rb') as stream:
                result[path.name] = hashlib.sha256(stream.read()).hexdigest()
    return result


def call(domain, module, function, *args, project_dir=None, **kwargs):
    if domain not in DOMAINS or not module.replace('_', '').isalnum():
        raise ValueError('未登记专业模块')
    folder = location(domain, project_dir)
    path = folder / (module + '.py')
    if not path.is_file() or not path.resolve().is_relative_to(folder):
        raise ValueError('独立工具缺少迁移接口，请使用支持本契约的版本；不会静默使用旧算法')
    before = fingerprint(folder)
    digest = hashlib.sha256(repr(sorted(before.items())).encode()).hexdigest()[:16]
    alias = '_workbench_specialist_' + DOMAINS[domain][0] + '_' + digest
    if alias not in sys.modules:
        package = types.ModuleType(alias);package.__path__ = [str(folder)];sys.modules[alias] = package
    name = alias + '.' + module
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        loaded = importlib.util.module_from_spec(spec);sys.modules[name] = loaded
        spec.loader.exec_module(loaded)
    target = getattr(sys.modules[name], function, None)
    if not callable(target):
        raise ValueError('独立迁移接口不匹配')
    result = target(*args, **kwargs)
    if before != fingerprint(folder):
        raise ValueError('专业工具方法在调用中变化，结果不视为同版本')
    LAST_PROVENANCE[domain] = dict(provider=DOMAINS[domain][0], module=module, function=function,
                                   methodFiles=before, selection='explicit-project-or-installed-package')
    return result
