"""Small offline first-use gateway; delegates research to existing implementations."""
import argparse
import csv
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_input(path):
    from collection_validation import unique_pairs, reject_constant, finite_json_float
    return json.loads(Path(path).read_text(encoding='utf-8-sig'),
                      object_pairs_hook=unique_pairs, parse_constant=reject_constant,
                      parse_float=finite_json_float)


def execute(command, destination, input_path=None, example='compare', question=None, as_of=None, online=False, codes=None, start=None, group=None):
    """Publish a complete result or a useful failure, without replacing user files."""
    destination = Path(destination)
    if destination.exists():
        return {'status': 'blocked', 'failureKind': 'output-exists',
                'message': '输出目录已有内容，本次没有覆盖。',
                'nextSteps': ['换一个尚不存在的 --out-dir 目录后重新运行。']}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.first-use-', dir=destination.parent) as temporary:
        stage = Path(temporary) / 'result'
        try:
            if sys.version_info < (3, 11):
                raise RuntimeError('此入口需要 Python 3.11 或更高版本')
            if command == 'doctor':
                from environment_check import inspect, markdown
                result = inspect()
                stage.mkdir()
                (stage / 'environment.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), 'utf-8')
                (stage / '环境检查.md').write_text(markdown(result), 'utf-8')
                summary = {'status': 'passed', 'mode': 'environment-check',
                           'message': '环境检查完成；未联网，未安装组件。',
                           'nextSteps': ['先运行 demo；缺少可选组件不妨碍标准库离线示例。']}
            elif command == 'ask':
                from research_question import run
                from research_brief_html import render
                if not question or not as_of:
                    raise ValueError('ask 需要 --question 和 --as-of；支持单家A股近一或三个月公告')
                spec = {'question': question, 'asOf': as_of, 'market': 'CN', 'onlineSearch': online, 'refresh': online}
                result = run(spec, stage)
                archive_file = Path(result['archivePath'])
                result['archivePath'] = str((destination.resolve() / archive_file.relative_to(stage)).resolve())
                archive_file.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), 'utf-8')
                (stage / '研究结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), 'utf-8')
                (stage / '研究结果.md').write_text(result['answer'], 'utf-8')
                (stage / '研究结果.html').write_text(render(result['answer'], 'A股公告变化研究'), 'utf-8')
                summary = {'status': result['status'], 'mode': 'announcement-research',
                           'message': '公告研究已留存，当前状态：' + result['status'],
                           'sourceVerification': 'not-verified', 'visualReview': 'not-performed',
                           'nextSteps': result['nextSteps']}
            elif command == 'snapshot':
                from quick_research import snapshot
                if not input_path or not as_of:
                    raise ValueError('snapshot 需要 --input 持仓CSV 与 --as-of 截止日')
                result = snapshot(input_path, stage, as_of)
                summary = {'status':result['status'], 'mode':'holdings-snapshot',
                           'message':'持仓结构报告已生成；底层风险与完整诊断尚未完成。',
                           'nextSteps':['打开持仓结构.html。','再提供底层持仓、历史序列与资金用途；不从名称猜行业或替用户设限。']}
            elif command == 'portfolio':
                from portfolio_history_report import publish
                if not input_path:
                    raise ValueError('portfolio 需要 --input 已有组合历史输入JSON')
                publish(load_input(input_path), stage)
                summary = {'status':'partial','mode':'historical-portfolio',
                           'message':'组合历史报告已生成；不等于真实账户收益或未来风险。',
                           'nextSteps':['打开组合历史风险观察.html；查看共同路径、收益贡献、相关性与资料限制。']}
            elif command == 'funds':
                from quick_research import fund_codes
                if not online:
                    raise ValueError('funds 需要主动启用 --online；已有净值文件请使用 compare')
                if not start or not as_of:
                    raise ValueError('funds 需要 --start 和 --as-of 明确历史区间')
                summary = fund_codes(codes, start, as_of, group, stage)
                summary['mode']='fund-code-comparison'
            else:
                mode = example if command == 'demo' else command
                if mode not in ('compare', 'news'):
                    raise ValueError('当前快速入口支持 compare 和 news')
                example_file = 'comparison-example.json' if mode == 'compare' else 'news-example.json'
                selected = ROOT / 'references/examples' / example_file if command == 'demo' else input_path
                if not selected:
                    raise ValueError('正式研究需要 --input 输入文件；首次试用请运行 demo')
                document = load_input(selected)
                if mode == 'compare':
                    from fund_comparison_brief import publish
                    publish(document, stage)
                else:
                    from retail_research import run
                    run(document, stage)
                summary = {'status': 'passed', 'mode': 'teaching-demo' if command == 'demo' else 'user-input-research',
                           'message': '已生成自然语言报告与输入底稿。',
                           'sourceVerification': 'not-verified', 'visualReview': 'not-performed',
                           'nextSteps': ['打开输出目录中的 HTML 或 Markdown 报告。',
                                         '教学示例不是实际基金或账户；正式研究请提供真实输入。'] if command == 'demo' else
                                        ['阅读报告中的结论、口径与缺口；来源真实性仍需核验。']}
        except (OSError, ValueError, TypeError, KeyError, RuntimeError, ImportError, ArithmeticError, csv.Error) as error:
            if isinstance(error, ImportError):
                kind, steps = 'missing-dependency', ['运行 doctor 查看当前依赖。', '按 references/standalone-install.md 安装本次功能需要的组件。']
            elif isinstance(error, FileNotFoundError):
                kind, steps = 'missing-input', ['确认 --input 文件存在；相对路径以当前终端目录为起点。', '首次试用可改用 demo，无须准备输入。']
            else:
                kind, steps = 'invalid-input-or-runtime', ['核对输入格式与日期、净值、分红口径。', '先运行 demo 区分输入问题和运行环境问题。']
            summary = {'status': 'blocked', 'failureKind': kind, 'message': str(error), 'nextSteps': steps}
            # Remove partial artifacts by leaving their temporary directory unpublished.
            failure_stage = Path(temporary) / 'failure'
            failure_stage.mkdir()
            stage = failure_stage
            (stage / '下一步.md').write_text('# 本次研究尚未完成\n\n' + summary['message'] + '\n\n' +
                                            '\n'.join('- ' + step for step in steps), 'utf-8')
        (stage / 'start-result.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), 'utf-8')
        if destination.exists():
            raise FileExistsError('输出目录在运行期间被创建，本次未覆盖')
        os.rename(stage, destination)
    return summary


def main():
    parser = argparse.ArgumentParser(description='快速研究入口；ask --online 才联网，不自动安装依赖。')
    parser.add_argument('command', choices=['demo', 'doctor', 'compare', 'news', 'ask', 'snapshot', 'portfolio', 'funds'])
    parser.add_argument('--input', type=Path)
    parser.add_argument('--example', choices=['compare', 'news'], default='compare')
    parser.add_argument('--out-dir', type=Path, required=True)
    parser.add_argument('--question', help='ask：单家A股近一或三个月公告问题')
    parser.add_argument('--as-of', help='ask：研究截止日 YYYY-MM-DD')
    parser.add_argument('--online', action='store_true', help='ask：主动查询身份候选与公告目录')
    parser.add_argument('--codes', nargs='+', help='funds：2至10个六位场外基金代码')
    parser.add_argument('--start', help='funds：历史起点 YYYY-MM-DD')
    parser.add_argument('--group', help='funds：用户声明的比较池名称，不代表同类认证')
    args = parser.parse_args()
    if args.command == 'demo' and args.input:
        parser.error('demo 使用教学输入；真实输入请用 compare 或 news')
    if args.command not in ('ask','funds') and args.online:
        parser.error('--online 仅用于 ask 或 funds')
    if args.command != 'ask' and args.question:
        parser.error('--question 仅用于 ask')
    if args.command not in ('ask','funds','snapshot') and args.as_of:
        parser.error('--as-of 用于 ask、funds 或 snapshot')
    if args.command != 'funds' and (args.codes or args.start or args.group):
        parser.error('--codes、--start、--group 仅用于 funds')
    if args.command == 'ask' and args.input:
        parser.error('ask 使用问题参数；已有消息文件请用 news')
    if args.command == 'funds' and args.input:
        parser.error('funds 使用代码取数；已有净值文件请用 compare')
    result = execute(args.command, args.out_dir, args.input, args.example, args.question, args.as_of, args.online, args.codes, args.start, args.group)
    print(result['message'])
    for step in result['nextSteps']:
        print('- ' + step)
    print('结果目录：' + str(args.out_dir.resolve()))
    return 0 if result['status'] in ('passed', 'partial') else 2


if __name__ == '__main__':
    raise SystemExit(main())
