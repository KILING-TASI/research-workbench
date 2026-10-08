"""Use the shared collector so identity, cache and failure gates stay consistent."""
import importlib.util
import sys
from pathlib import Path

_PATH = Path(__file__).resolve().parents[3] / 'scripts' / 'portable_collect.py'
_NAME = '_research_workbench_shared_portable_collect'
if not _PATH.is_file():
    raise FileNotFoundError('ETF独立取数需要完整research-workbench包；缺少共享取数器，不回退旧缓存逻辑')
if str(_PATH.parent) not in sys.path:
    sys.path.insert(0, str(_PATH.parent))
if _NAME not in sys.modules:
    _spec = importlib.util.spec_from_file_location(_NAME, _PATH)
    _module = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_module)
    sys.modules[_NAME] = _module
else:
    _module = sys.modules[_NAME]
get = _module.get
named = _module.named
collect = _module.collect
