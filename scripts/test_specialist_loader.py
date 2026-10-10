import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from specialist_loader import call, LAST_PROVENANCE


class TestSpecialistLoader(unittest.TestCase):
    def test_identical_source_different_projects_executes_selected_origin(self):
        with tempfile.TemporaryDirectory() as tmp:
            origins=[]
            for label in ('first','second'):
                root=Path(tmp)/label;folder=root/'cnreconcile';folder.mkdir(parents=True)
                (folder/'__init__.py').write_text('',encoding='utf-8')
                (folder/'probe.py').write_text('def origin():\n return __file__\n',encoding='utf-8')
                result=call('financial','probe','origin',project_dir=root)
                self.assertEqual(Path(result).resolve(),(folder/'probe.py').resolve())
                self.assertEqual(LAST_PROVENANCE['financial']['selectedFolder'],str(folder.resolve()))
                self.assertEqual(LAST_PROVENANCE['financial']['moduleOrigins']['probe'],str((folder/'probe.py').resolve()))
                origins.append(result)
            self.assertNotEqual(origins[0],origins[1])

    def test_failed_initialization_and_imported_helper_are_not_cached(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'cnreconcile';folder.mkdir();(folder/'__init__.py').write_text('',encoding='utf-8')
            (folder/'helper.py').write_text("from pathlib import Path\np=Path(__file__).with_suffix('.attempts')\np.write_text(str(int(p.read_text())+1) if p.exists() else '1')\n",encoding='utf-8')
            (folder/'probe.py').write_text("from . import helper\ndef answer():\n return 42\nraise RuntimeError('initialization failed')\n",encoding='utf-8')
            for attempt in (1,2):
                with self.assertRaisesRegex(RuntimeError,'initialization failed'):
                    call('financial','probe','answer',project_dir=tmp)
                self.assertEqual((folder/'helper.attempts').read_text(),str(attempt))
                self.assertNotIn('financial',LAST_PROVENANCE)
            (folder/'probe.py').write_text('from . import helper\ndef answer():\n return 99\n',encoding='utf-8')
            self.assertEqual(call('financial','probe','answer',project_dir=tmp),99)
            self.assertEqual((folder/'helper.attempts').read_text(),'3')

    def test_nested_source_change_with_same_timestamp_uses_new_method(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'cnreconcile';nested=folder/'nested';nested.mkdir(parents=True)
            (folder/'__init__.py').write_text('',encoding='utf-8');(nested/'__init__.py').write_text('',encoding='utf-8')
            helper=nested/'helper.py';helper.write_text('value=42\n',encoding='utf-8')
            (folder/'probe.py').write_text('from .nested.helper import value\ndef answer():\n return value\n',encoding='utf-8')
            self.assertEqual(call('financial','probe','answer',project_dir=tmp),42)
            identity=LAST_PROVENANCE['financial']['methodIdentitySha256'];stamp=helper.stat()
            helper.write_text('value=43\n',encoding='utf-8');os.utime(helper,ns=(stamp.st_atime_ns,stamp.st_mtime_ns))
            self.assertEqual(call('financial','probe','answer',project_dir=tmp),43)
            self.assertNotEqual(identity,LAST_PROVENANCE['financial']['methodIdentitySha256'])
            self.assertIn('nested/helper.py',LAST_PROVENANCE['financial']['methodFiles'])
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
