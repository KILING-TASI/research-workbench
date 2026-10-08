"""Reuse the workbench ETF evaluation kernel; keep evidence gates identical."""
import importlib.util
import sys
from pathlib import Path

_PATH = Path(__file__).resolve().parents[3] / 'scripts' / 'etf_evaluation.py'
_NAME = '_research_workbench_shared_etf_evaluation'
if not _PATH.is_file():
    raise FileNotFoundError('ETF评价需完整research-workbench包；缺少共享评价内核，不回退旧算法')
if _NAME not in sys.modules:
    _spec = importlib.util.spec_from_file_location(_NAME, _PATH)
    _module = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_module)
    sys.modules[_NAME] = _module
else:
    _module = sys.modules[_NAME]
num = _module.num
evaluate_layers = _module.evaluate_layers
