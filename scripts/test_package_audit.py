import tempfile,unittest,zipfile
from pathlib import Path
from package_audit import audit
class Tests(unittest.TestCase):
 def test_research_records_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'SKILL.md').write_text('skill');z=p/'a.zip'
   with zipfile.ZipFile(z,'w') as f:f.writestr('research-workbench/SKILL.md','skill');f.writestr('research-workbench/research/tasks/user.json','{}')
   self.assertFalse(audit(z,p)['passed'])
 def test_missing_and_changed(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'SKILL.md').write_text('new');z=p/'a.zip'
   with zipfile.ZipFile(z,'w') as f:f.writestr('research-workbench/SKILL.md','old')
   self.assertFalse(audit(z,p)['passed'])
 def test_clean(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'SKILL.md').write_text('skill');z=p/'a.zip'
   with zipfile.ZipFile(z,'w') as f:f.writestr('research-workbench/SKILL.md','skill')
   self.assertTrue(audit(z,p)['passed'])
 def test_license_included_and_required_when_present(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'SKILL.md').write_text('skill');(p/'LICENSE').write_text('MIT License');z=p/'a.zip'
   with zipfile.ZipFile(z,'w') as f:f.writestr('research-workbench/SKILL.md','skill')
   self.assertFalse(audit(z,p)['passed'])
   with zipfile.ZipFile(z,'w') as f:f.writestr('research-workbench/SKILL.md','skill');f.writestr('research-workbench/LICENSE','MIT License')
   self.assertTrue(audit(z,p)['passed'])
 def test_disclaimer_required_in_package_when_present(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'SKILL.md').write_text('skill');(p/'DISCLAIMER.md').write_text('Research only');z=p/'a.zip'
   with zipfile.ZipFile(z,'w') as f:f.writestr('research-workbench/SKILL.md','skill')
   self.assertFalse(audit(z,p)['passed'])
   with zipfile.ZipFile(z,'w') as f:f.writestr('research-workbench/SKILL.md','skill');f.writestr('research-workbench/DISCLAIMER.md','Research only')
   self.assertTrue(audit(z,p)['passed'])
 def test_third_party_notice_required_when_present(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'SKILL.md').write_text('skill');(root/'THIRD_PARTY_NOTICES.md').write_text('scope');archive=root/'a.zip'
   with zipfile.ZipFile(archive,'w') as z:z.writestr('research-workbench/SKILL.md','skill')
   self.assertFalse(audit(archive,root)['passed'])
   with zipfile.ZipFile(archive,'w') as z:z.writestr('research-workbench/SKILL.md','skill');z.writestr('research-workbench/THIRD_PARTY_NOTICES.md','scope')
   self.assertTrue(audit(archive,root)['passed'])
if __name__=='__main__':unittest.main()
