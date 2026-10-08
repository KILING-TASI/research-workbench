"""Check resources before project-backed operations; never download or fabricate them."""
import argparse
import json
from pathlib import Path

RESOURCES = {
    'update': ['assets/data.json', 'assets/calendar-verified-fields.json',
               'assets/bjx-panel.html', 'assets/workbench.html',
               'assets/bjx-workbench.css', 'assets/bjx-workbench.js', 'assets/workbench-shell.css',
               'assets/workbench-shell.js', 'assets/workbench-theme.css',
               'assets/cash-ledger.js', 'assets/cash-plan.js',
               'assets/cash-repo-plan.js', 'assets/cash-plan-example.json'],
    'historical-cash': ['assets/data.json', 'assets/calendar-verified-fields.json',
                        'assets/bse-trading-calendar-2026.json'],
}


def inspect(root, operation, overrides=None):
    if operation not in RESOURCES:
        raise ValueError('Unknown operation')
    overrides = overrides or {}
    if set(overrides) - set(RESOURCES[operation]):
        raise ValueError('Unknown resource override')
    missing = [name for name in RESOURCES[operation]
               if not Path(overrides.get(name, Path(root) / name)).is_file()]
    return {'operation': operation, 'status': 'resources-present' if not missing else 'missing-resources',
            'missingResources': missing, 'networkAttempted': False,
            'boundary': '仅检查文件是否存在，不证明数据新鲜、原文核验通过或计算正确。',
            'guidance': '缺少项目资料时不能运行此路径；可使用独立证据查询和显式输入的获配/现金测算。'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=RESOURCES)
    args = parser.parse_args()
    result = inspect(Path(__file__).resolve().parents[1], args.operation)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'resources-present' else 2


if __name__ == '__main__':
    raise SystemExit(main())
