from pathlib import Path
import importlib.util
import sys
from setuptools import setup

spec = importlib.util.spec_from_file_location("_build_skill", Path(__file__).with_name("_build_skill.py"))
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
setup(cmdclass={"build_py": module.BuildSkill})
