"""Run the distributed JavaScript tests on each CI operating system."""
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[2]
node = shutil.which('node')
if not node:
    raise SystemExit('Node.js is required for JavaScript validation')
tests = sorted(list((root / 'scripts').glob('test*.js')) +
               list((root / 'modules').glob('*/scripts/test*.js')))
if not tests:
    raise SystemExit('No JavaScript tests found')
for test in tests:
    print('Running ' + test.relative_to(root).as_posix(), flush=True)
    subprocess.run([node, str(test)], cwd=root, check=True, timeout=60)
print('Passed ' + str(len(tests)) + ' JavaScript test files')
