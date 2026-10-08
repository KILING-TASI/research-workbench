import tempfile,unittest,zipfile
from pathlib import Path
from build_package import build
from package_audit import allowed,source_file
class PortablePackage(unittest.TestCase):
 def test_raw_documents_not_distributed(self):
  self.assertFalse(allowed('references/company.pdf'));self.assertFalse(allowed('scripts/user.xlsx'));self.assertFalse(allowed('modules/key.env'))
 def test_external_source_link_rejected(self):
  with tempfile.TemporaryDirectory() as root:
   source=Path(root)/'source';(source/'scripts').mkdir(parents=True);(source/'SKILL.md').write_text('test');external=Path(root)/'external.py';external.write_text('private')
   try:(source/'scripts/external.py').symlink_to(external)
   except OSError as error:
    if getattr(error,'winerror',None)==1314:self.skipTest('当前Windows无符号链接创建权限；真实链接场景未验证')
    raise
   with self.assertRaises(ValueError):build(source,Path(root)/'package.zip')
   self.assertFalse((Path(root)/'package.zip').exists())
 def test_resolved_path_outside_source_rejected(self):
  with tempfile.TemporaryDirectory() as root:
   source=Path(root)/'source';source.mkdir();external=Path(root)/'external.py';external.write_text('private')
   with self.assertRaises(ValueError):source_file(source,external)
 def test_install_material_and_example_included_no_user_cache(self):
  with tempfile.TemporaryDirectory() as root:
   source=Path(root)/'source';source.mkdir()
   for name in ['SKILL.md','README.md','references/requirements-optional.txt','references/examples/news-example.json','scripts/main.py','private.json','README.md-private']:
    path=source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('test','utf-8')
   result=build(source,Path(root)/'package.zip');self.assertTrue(result['passed'])
   with zipfile.ZipFile(Path(root)/'package.zip') as z:
    self.assertIn('research-workbench/README.md',z.namelist());self.assertIn('research-workbench/references/examples/news-example.json',z.namelist());self.assertNotIn('research-workbench/private.json',z.namelist());self.assertNotIn('research-workbench/README.md-private',z.namelist())
 def test_old_package_preserved(self):
  with tempfile.TemporaryDirectory() as root:
   out=Path(root)/'package.zip';out.write_bytes(b'old')
   with self.assertRaises(FileExistsError):build(Path(root),out)
   self.assertEqual(out.read_bytes(),b'old')
 def test_exact_root_file_allowlist(self):
  self.assertTrue(allowed('README.md'));self.assertFalse(allowed('README.md-private'));self.assertFalse(allowed('SKILL.md-old'))
