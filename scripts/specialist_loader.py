"""Thin trusted-library selection. No discovery, downloads, installs or algorithm fallback."""
import hashlib
import ast
import importlib.util
import importlib.abc
import importlib.machinery
import os
from pathlib import Path
import sys
import types

DOMAINS = {
    'lookthrough': ('cnlookthrough', 'RESEARCH_WORKBENCH_LOOKTHROUGH_DIR'),
    'financial': ('cnreconcile', 'RESEARCH_WORKBENCH_FINANCIAL_DIR'),
    'portfolio': ('portfolio_engine', 'RESEARCH_WORKBENCH_PORTFOLIO_DIR'),
    'etf': ('cn_etf_rotation', 'RESEARCH_WORKBENCH_ETF_DIR'),
}
LAST_PROVENANCE = {}


class SpecialistUnavailableError(ValueError):
    def __init__(self, message, dependency_record=None):
        super().__init__(message)
        self.dependency_record = dependency_record


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
        raise SpecialistUnavailableError('独立工具不可用：请安装对应专业包，或明确设置' + variable + '为可信项目目录；不会自动下载安装或回到重复算法')
    return folder.resolve()


def fingerprint(folder):
    result = {}
    for path in sorted(folder.rglob('*.py')):
        if path.is_file():
            if not path.resolve().is_relative_to(folder):
                raise ValueError('专业方法文件越出所选目录')
            with open(path, 'rb') as stream:
                result[path.relative_to(folder).as_posix()] = hashlib.sha256(stream.read()).hexdigest()
    return result


def method_identity(folder, methods):
    return hashlib.sha256(repr((os.path.normcase(str(folder)), sorted(methods.items()))).encode('utf-8')).hexdigest()


def check(domain, module, function, project_dir=None):
    """Locate one declared interface without importing or executing professional code."""
    if domain not in DOMAINS or not module.replace('_', '').isalnum():
        raise ValueError('未登记专业模块')
    package, variable = DOMAINS[domain]
    distribution = {'lookthrough': 'cn-fund-lookthrough', 'financial': 'cn-financial-reconcile',
                    'portfolio': 'portfolio-decision-engine', 'etf':'cn-etf-rotation-engine'}[domain]
    record = dict(provider=package, module=module, function=function, available=False,
                  selectedFolder=None, moduleOrigins={}, methodFiles={}, methodIdentitySha256=None,
                  selection='explicit-project-or-installed-package', loadState='not-executed',
                  dataStatus='not-checked', distribution=distribution,
                  nextSteps=['使用兼容的' + distribution + '专业源码或wheel；不以旧发布包默认替代。',
                             '可安装该工具到当前Python环境，或设置' + variable + '为可信项目根目录；不自动下载安装。'],
                  limitations=['只检查软件目录及函数声明，不加载专业代码，不认证数据或实际计算。'])
    try:
        folder = location(domain, project_dir)
        record['selectedFolder'] = str(folder)
        path = folder / (module + '.py')
        if not path.is_file() or not path.resolve().is_relative_to(folder):
            raise SpecialistUnavailableError('独立工具缺少迁移接口，请使用支持本契约的版本；不会静默使用旧算法')
        before = fingerprint(folder)
        with open(path, 'rb') as stream:
            tree = ast.parse(stream.read(), filename=str(path))
        if not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function for node in tree.body):
            raise SpecialistUnavailableError('独立工具缺少所需函数声明：' + module + '.' + function)
        if before != fingerprint(folder):
            raise ValueError('专业方法在检查期间变化，请另行重试')
        record.update(available=True, status='located-not-executed', message='专业接口可定位，尚未加载或验证计算。',
                      selectedModuleFile=str(path.resolve()), methodFiles=before,
                      methodIdentitySha256=method_identity(folder, before), nextSteps=[])
    except SpecialistUnavailableError as error:
        record.update(status='specialist-unavailable', message=str(error))
    except (OSError, ValueError, SyntaxError, ImportError) as error:
        record.update(status='software-source-unconfirmed', message='专业软件来源未能检查：' + str(error))
    return record


def require(domain, module, function, project_dir=None):
    record = check(domain, module, function, project_dir)
    if not record['available']:
        raise SpecialistUnavailableError(record['message'], record)
    return record


class SourceLoader(importlib.machinery.SourceFileLoader):
    def get_code(self, fullname):
        # The method identity is source bytes, not timestamp-based cached bytecode.
        return self.source_to_code(self.get_data(self.path), self.path)


class NamespaceFinder(importlib.abc.MetaPathFinder):
    def __init__(self, alias, folder):
        self.alias, self.folder = alias, folder

    def find_spec(self, fullname, path=None, target=None):
        if not fullname.startswith(self.alias + '.'):
            return None
        relative = fullname[len(self.alias) + 1:].replace('.', '/')
        for candidate in (self.folder / (relative + '.py'), self.folder / relative / '__init__.py'):
            if candidate.is_file() and candidate.resolve().is_relative_to(self.folder):
                return importlib.util.spec_from_file_location(fullname, candidate,
                    loader=SourceLoader(fullname, str(candidate)))
        raise ModuleNotFoundError('所选专业目录缺少模块：' + fullname)


def clear_namespace(alias):
    for name in list(sys.modules):
        if name == alias or name.startswith(alias + '.'):
            sys.modules.pop(name, None)


def verify_origins(alias, folder, methods):
    if list(getattr(sys.modules[alias], '__path__', [])) != [str(folder)]:
        raise ValueError('专业命名空间目录与所选目录不符')
    origins = {}
    for name, loaded in list(sys.modules.items()):
        if not name.startswith(alias + '.'):
            continue
        relative = name[len(alias) + 1:].replace('.', '/')
        candidates = (folder / (relative + '.py'), folder / relative / '__init__.py')
        origin = Path(getattr(loaded, '__file__', '')).resolve()
        declared = getattr(getattr(loaded, '__spec__', None), 'origin', None)
        if (not declared or Path(declared).resolve() != origin or
                not any(p.is_file() and p.resolve() == origin for p in candidates) or
                not origin.is_relative_to(folder) or origin.relative_to(folder).as_posix() not in methods):
            raise ValueError('已加载专业模块来源与所选方法不符')
        origins[name[len(alias) + 1:]] = str(origin)
    return origins


def call(domain, module, function, *args, project_dir=None, **kwargs):
    if domain not in DOMAINS or not module.replace('_', '').isalnum():
        raise ValueError('未登记专业模块')
    folder = location(domain, project_dir)
    path = folder / (module + '.py')
    if not path.is_file() or not path.resolve().is_relative_to(folder):
        raise SpecialistUnavailableError('独立工具缺少迁移接口，请使用支持本契约的版本；不会静默使用旧算法')
    before = fingerprint(folder)
    LAST_PROVENANCE.pop(domain, None)
    digest = method_identity(folder, before)
    alias = '_workbench_specialist_' + DOMAINS[domain][0] + '_' + digest
    if alias not in sys.modules:
        package = types.ModuleType(alias);package.__path__ = [str(folder)];sys.modules[alias] = package
    name = alias + '.' + module
    finder = NamespaceFinder(alias, folder)
    sys.meta_path.insert(0, finder)
    try:
        if name not in sys.modules:
            spec = finder.find_spec(name)
            loaded = importlib.util.module_from_spec(spec);sys.modules[name] = loaded
            try:
                spec.loader.exec_module(loaded)
            except BaseException:
                clear_namespace(alias)
                raise
        try:
            verify_origins(alias, folder, before)
        except BaseException:
            clear_namespace(alias)
            raise
        target = getattr(sys.modules[name], function, None)
        if not callable(target):
            raise ValueError('独立迁移接口不匹配')
        result = target(*args, **kwargs)
        if before != fingerprint(folder):
            clear_namespace(alias)
            raise ValueError('专业工具方法在调用中变化，结果不视为同版本')
        try:
            origins = verify_origins(alias, folder, before)
        except BaseException:
            clear_namespace(alias)
            raise
    finally:
        sys.meta_path.remove(finder)
    LAST_PROVENANCE[domain] = dict(provider=DOMAINS[domain][0], module=module, function=function,
                                   methodFiles=before, selectedFolder=str(folder), moduleOrigins=origins,
                                   methodIdentitySha256=digest, selection='explicit-project-or-installed-package')
    return result
