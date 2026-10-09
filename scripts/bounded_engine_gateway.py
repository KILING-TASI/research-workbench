"""Opt-in native contracts. Preserves responses; never installs or replaces engines."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from independent_engine import load

ENGINES = ('bjx', 'portfolio-observed', 'portfolio-cash-demand', 'convertible', 'rules')


def fingerprint(root):
    paths = list(root.glob('*.py')) + [root / 'pyproject.toml']
    for folder in ('src/portfolio_engine', 'cbengine', 'bjx_engine', 'scripts', 'rules'):
        directory = root / folder
        if directory.is_dir():
            paths += list(directory.rglob('*.py')) + list(directory.rglob('*.json'))
    result = {}
    for path in paths:
        if path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root):
            result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def reject_bjx_extensions(spec):
    data = spec.get('input')
    if not isinstance(data, dict):
        return  # Native malformed-input failure is preserved, not fabricated here.
    operation = spec.get('operation')
    if operation == 'scenario.v1':
        allowed = {'capital', 'budget', 'issue_price', 'max_subscription_shares', 'subscription_date',
                   'refund_available_date', 'sale_cash_available_date', 'annual_cash_cost_rate', 'fees', 'scenarios'}
        if set(data) - allowed:
            raise ValueError('北交原生桥不支持额外年度、融资或概率字段')
        fees = data.get('fees')
        if isinstance(fees, dict) and set(fees) - {'commission_rate', 'minimum_commission', 'stamp_rate', 'transfer_rate'}:
            raise ValueError('北交原生桥不支持滑点或额外费用，不能静默忽略')
        rows = data.get('scenarios')
        if isinstance(rows, list) and any(isinstance(row, dict) and set(row) - {'id', 'allocation_rate', 'listing_return', 'basis'} for row in rows):
            raise ValueError('本轮仅无权重单发行情景，不支持概率或额外情景字段')
    elif operation == 'cash_ledger.v1':
        if set(data) - {'initial_cash', 'calendar', 'events'}:
            raise ValueError('现金账本不支持额外年度或成本字段')
        rows = data.get('events')
        allowed = {'id', 'instrument', 'kind', 'amount', 'date', 'evidence', 'order', 'timing_evidence', 'principal_released'}
        if isinstance(rows, list) and any(isinstance(row, dict) and set(row) - allowed for row in rows):
            raise ValueError('现金事件包含未支持字段，不静默忽略')


def revision(root):
    result = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, capture_output=True, text=True, timeout=10)
    return result.stdout.strip() if result.returncode == 0 else None


def run(engine, project_dir, input_path, out_dir, engine_python=None, timeout=60):
    if engine not in ENGINES:
        raise ValueError('不支持的独立契约')
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 60:
        raise ValueError('超时须为1至60秒')
    root = Path(project_dir).resolve()
    source = Path(input_path).resolve()
    destination = Path(out_dir).absolute()
    if not root.is_dir() or destination.exists():
        raise ValueError('须提供可信本地项目与新的结果目录；不会下载或安装')
    spec = load(source)
    if not isinstance(spec, dict):
        raise ValueError('原生输入须为对象')
    if engine == 'bjx':
        reject_bjx_extensions(spec)
    input_bytes = source.read_bytes()
    python = str(Path(engine_python).resolve()) if engine_python else sys.executable
    if not Path(python).is_file():
        raise ValueError('指定Python不存在')
    before = fingerprint(root)
    gateway_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if not before:
        raise ValueError('项目代码缺失')
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    env.pop('PYTHONPATH', None)
    env.pop('PYTHONHOME', None)
    with tempfile.TemporaryDirectory(prefix='bounded-native-') as temporary:
        stage = Path(temporary)
        native_input = stage / 'input.json'
        native_input.write_bytes(input_bytes)
        if load(native_input) != spec:
            raise ValueError('输入快照与已校验对象不同')
        native_output = stage / 'native-output'
        cwd = root
        stdin = None
        if engine == 'bjx':
            entry = root / 'api.py'
            command = [python, '-S', str(entry)]
            stdin = native_input.read_text('utf-8-sig')
        elif engine in ('portfolio-observed', 'portfolio-cash-demand'):
            cwd = root / 'src'
            entry = cwd / 'portfolio_engine/__main__.py'
            operation = 'workbench-observed-cashflow' if engine == 'portfolio-observed' else 'cash-demand'
            command = [python, '-m', 'portfolio_engine', operation, '--input', str(native_input), '--out', str(native_output)]
        elif engine == 'convertible':
            entry = root / 'cbengine/bridge.py'
            command = [python, '-m', 'cbengine.bridge', str(native_input), '--out-dir', str(native_output)]
        else:
            entry = root / 'scripts/common_interface.py'
            command = [python, str(entry), '--input', str(native_input)]
        if not entry.is_file() or not entry.resolve().is_relative_to(root):
            raise ValueError('项目不具备指定原生入口')
        completed = subprocess.run(command, cwd=cwd, env=env, input=stdin, capture_output=True,
                                   text=True, encoding='utf-8', timeout=timeout)
        if fingerprint(root) != before:
            raise ValueError('调用期间源码变化，不能保存为同一方法结果')
        response = None
        if engine in ('bjx', 'rules'):
            try:
                response = json.loads(completed.stdout)
            except (ValueError, TypeError):
                pass
        elif completed.returncode == 0:
            filename = 'compatibility-result.json' if engine == 'portfolio-observed' else 'cash-demand.json' if engine == 'portfolio-cash-demand' else 'result.json'
            response = load(native_output / filename)
        rule_roundtrip = None
        if engine == 'rules' and completed.returncode == 0 and isinstance(response, dict):
            if response.get('contract_version') != 'cn-market-rules.rule-handoff/1.0' or response.get('origin_interface_version') != '1.2':
                raise ValueError('规则消费本轮仅核对信封1.2/交接1.0，不静默支持其他版本')
            common_path = stage / 'common.json'
            common_path.write_text(json.dumps(response, ensure_ascii=False, allow_nan=False), encoding='utf-8')
            reverse = subprocess.run([python, str(entry), '--reverse', '--input', str(common_path)],
                                     cwd=root, env=env, capture_output=True, text=True, encoding='utf-8', timeout=timeout)
            if reverse.returncode != 0 or json.loads(reverse.stdout) != spec:
                raise ValueError('规则交接回转不一致，不能认证无损消费')
            rule_roundtrip = 'same-producer-roundtrip-verified'
        if fingerprint(root) != before or hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != gateway_sha:
            raise ValueError('源码或规则目录变化，未保存为同一方法结果')
        # A native failed/infeasible response is preserved, never upgraded to success.
        status = 'native-response-preserved' if completed.returncode == 0 and response is not None else 'blocked'
        wrapper = dict(gatewayMethodVersion='bounded-native-gateway-1', engine=engine, status=status,
                       engine_response=response, nativeReturnCode=completed.returncode,
                       nativeError=completed.stderr.strip()[-2000:] or None,
                       inputSha256=hashlib.sha256(native_input.read_bytes()).hexdigest(),
                       workbenchCommit=revision(Path(__file__).resolve().parents[1]), engineCommit=revision(root),
                       methodFiles=before,
                       gatewaySourceSha256=gateway_sha,
                       ruleRoundtripStatus=rule_roundtrip,
                       scope='原生输入与输出保留；不认证模型等价、资料完整性、账户或实际资格；不替换内置入口')
        destination.mkdir(parents=True)
        (destination / 'input.json').write_bytes(native_input.read_bytes())
        (destination / 'result.json').write_text(json.dumps(wrapper, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        if engine == 'rules' and response is not None:
            from research_brief_html import render
            body = '# 规则版本与证据观察\n\n版本选择不等于项目资格通过。下面只保留本次选定目录和证据状态，未知仍是未知。\n\n'
            body += '交接版本：' + response['contract_version'] + '；截止日期：' + str(response.get('as_of')) + '。\n\n'
            originals = {row['record_id']: row for row in response.get('legacy_payload', {}).get('records', [])}
            for row in response.get('records', []):
                selection = row.get('rule_selection', {})
                original = originals.get(row['record_id'], {})
                labels = {'selected': '已选定规则版本', 'gap': '所给日期没有已匹配的适用版本', 'unknown': '资料不足', 'ambiguous': '存在多个候选版本', 'conditional': '适用仍有条件', 'deferred': '尚未生效'}
                query = selection.get('query', {})
                body += '## ' + row.get('entity_name', row['record_id']) + '\n\n' + labels.get(selection.get('status'), str(selection.get('status', 'unknown'))) + '。规则标识：' + str(selection.get('rule_version_id') or '未知') + '。\n\n'
                body += '适用日期：' + str(query.get('applicability_date') or '未知') + '；知识截止日期：' + str(query.get('knowledge_date') or '未知') + '。两个日期不同，当前回溯判断不能冒充当时已知结果。\n\n'
                body += '项目层核对：' + ('仅完成部分核对' if original.get('rule_check_status') == 'partial' else '未知或尚有缺口') + '；不据此认定实际可执行。原始状态：' + str(original.get('rule_check_status', 'unknown')) + '。\n\n'
                for fact in row.get('facts', []):
                    body += fact['key'] + '：' + ('未知' if fact.get('value') is None else str(fact['value'])) + '；证据状态' + str(fact.get('status')) + '；' + str(fact.get('reason', '')) + '\n\n'
            for source_record in response.get('sources', []):
                body += '来源：' + str(source_record.get('url')) + '；等级' + str(source_record.get('source_tier')) + '；日期' + json.dumps(source_record.get('dates'), ensure_ascii=False) + '；核验' + json.dumps(source_record.get('verification'), ensure_ascii=False) + '\n\n'
            (destination / '规则观察.md').write_text(body, encoding='utf-8')
            (destination / '规则观察.html').write_text(render(body, '规则版本与证据观察'), encoding='utf-8')
        return wrapper


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('engine', choices=ENGINES)
    parser.add_argument('--project-dir', required=True)
    parser.add_argument('--input', required=True)
    parser.add_argument('--out-dir', required=True)
    parser.add_argument('--engine-python')
    args = parser.parse_args()
    try:
        result = run(args.engine, args.project_dir, args.input, args.out_dir, args.engine_python)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        raise SystemExit(0 if result['status'] == 'native-response-preserved' else 2)
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        parser.exit(2, '未完成独立契约调用：' + str(error) + '\n')
