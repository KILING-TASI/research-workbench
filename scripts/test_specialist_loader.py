import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from specialist_loader import call


class TestSpecialistLoader(unittest.TestCase):
    def test_missing_explicit_tool_never_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'不会自动下载安装或回到重复算法'):
                call('financial','original_compat','verify',{},project_dir=tmp)
    def test_installed_old_tool_without_contract_fails_clearly(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'cnreconcile';folder.mkdir();(folder/'__init__.py').write_text('',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'缺少迁移接口'):
                call('financial','original_compat','verify',{},project_dir=tmp)
    def test_source_change_during_call_is_not_same_method(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'cnreconcile';folder.mkdir();(folder/'__init__.py').write_text('',encoding='utf-8')
            (folder/'original_compat.py').write_text("from pathlib import Path\ndef verify(spec):\n Path(__file__).write_text('# changed')\n return {'status':'passed'}\n",encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'调用中变化'):
                call('financial','original_compat','verify',{},project_dir=tmp)
