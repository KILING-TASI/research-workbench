"""Reuse the full workbench replacement research kernel; no legacy fallback."""
import importlib.util
import sys
from pathlib import Path
_SCRIPT_DIR=Path(__file__).resolve().parents[3]/'scripts'
_PATH=_SCRIPT_DIR/'replacement_research.py'
if not _PATH.is_file():raise FileNotFoundError('ETF替换研究需完整research-workbench包，缺少共享内核')
if str(_SCRIPT_DIR) not in sys.path:sys.path.insert(0,str(_SCRIPT_DIR))
_NAME='_research_workbench_shared_replacement'
if _NAME not in sys.modules:
    _spec=importlib.util.spec_from_file_location(_NAME,_PATH)
    _module=importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_module)
    sys.modules[_NAME]=_module
else:_module=sys.modules[_NAME]
number=_module.number
evaluate=_module.evaluate
main=_module.main
if __name__=='__main__':main()
