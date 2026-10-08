"""Audit registered capabilities without fetching data or changing models."""
import argparse
import datetime
import hashlib
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def safe_path(workspace, relative):
    path = (workspace / relative).resolve()
    if not path.is_relative_to(workspace):
        raise ValueError('能力路径超出工作目录')
    return path

def audit(workspace, run_checks=False, node=None):
    workspace = Path(workspace).resolve()
    registry = json.loads((ROOT / 'references/capabilities.json').read_text(encoding='utf-8'))
    runtime = node or shutil.which('node')
    results = []
    executed = {}
    for item in registry['capabilities']:
        result = {**item, 'dataAvailable': False, 'recordCount': None, 'checksResult': [], 'complete': False}
        try:
            data = json.loads(safe_path(workspace, item['dataPath']).read_text(encoding='utf-8'))
            records = data
            for key in item['recordsKey'].split('.') if item['recordsKey'] else []:
                records = records[key]
            if not isinstance(records, (dict, list)):
                raise ValueError('登记的记录字段不是集合')
            result.update(dataAvailable=True, recordCount=len(records),
                          snapshotTime=(data.get('fetchedAt') or data.get('retrievedAt') or data.get('updatedAt')) if isinstance(data, dict) else None,
                          countMeaning='缓存记录数，非模型可用或已核验数量')
        except (OSError, ValueError, KeyError, TypeError) as error:
            result['dataIssue'] = str(error)
        result['entrypointStatus'] = {}
        result['entrypointIssues'] = {}
        for entrypoint in item['entrypoints']:
            try:
                result['entrypointStatus'][entrypoint] = safe_path(workspace, entrypoint).is_file()
            except (OSError, ValueError, TypeError) as error:
                result['entrypointStatus'][entrypoint] = False
                result['entrypointIssues'][entrypoint] = str(error)
        for script in item['checks']:
            if script not in executed:
                check = {'script': script, 'status': 'not-run'}
                try:
                    path = safe_path(workspace, script)
                except (OSError, ValueError, TypeError) as error:
                    check.update(status='failed', output=str(error))
                    executed[script] = check
                    result['checksResult'].append(check)
                    continue
                if not path.is_file():
                    check['status'] = 'missing'
                elif run_checks:
                    javascript = path.suffix in ['.js', '.cjs', '.mjs']
                    if javascript and not runtime:
                        check.update(status='failed', output='缺少Node.js；请安装或通过--node指定运行程序')
                        executed[script] = check
                        result['checksResult'].append(check)
                        continue
                    command = [str(runtime), str(path)] if javascript else [sys.executable, str(path)]
                    try:
                        process = subprocess.run(command, cwd=workspace, capture_output=True, text=True,
                                                 encoding='utf-8', errors='replace', timeout=45)
                        check.update(status='passed' if process.returncode == 0 else 'failed',
                                     exitCode=process.returncode, output=(process.stdout + process.stderr)[-1500:])
                    except (OSError, subprocess.TimeoutExpired) as error:
                        check.update(status='failed', output=str(error))
                executed[script] = check
            result['checksResult'].append(executed[script])
        result['status'] = 'partial' if result['dataAvailable'] else 'data-unavailable'
        result['validationScope'] = '缓存结构及登记计算检查；未联网核验、未视觉验收、未证明模型有效'
        results.append(result)
    return {'type': 'workbench-capability-audit', 'version': 1,
            'checkedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'dataRefreshed': False, 'capabilityCount': len(results), 'capabilities': results,
            'testSummary': {s: sum(c['status'] == s for c in executed.values()) for s in ['passed', 'failed', 'missing', 'not-run']}}

def save(workspace, report):
    path = workspace / 'outputs/bjx-newshare-toolkit/assets/功能排查.json'
    if path.exists():
        old = path.read_bytes()
        archive = workspace / 'outputs/bjx-newshare-toolkit/research/audit-history' / (hashlib.sha256(old).hexdigest() + '.json')
        archive.parent.mkdir(parents=True, exist_ok=True)
        if not archive.exists():
            archive.write_bytes(old)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.audit-', suffix='.tmp', dir=path.parent)
    temp = Path(name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(json.dumps(report, ensure_ascii=False, indent=2))
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()
    return path

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=Path.cwd())
    parser.add_argument('--run-checks', action='store_true')
    parser.add_argument('--node', help='由调用者指定的Node.js路径；默认从PATH查找')
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    report = audit(workspace, args.run_checks, args.node)
    output = save(workspace, report)
    print(json.dumps({'report': str(output), 'capabilities': report['capabilityCount'], 'checks': report['testSummary']}, ensure_ascii=False))
    sys.exit(1 if report['testSummary']['failed'] else 0)
