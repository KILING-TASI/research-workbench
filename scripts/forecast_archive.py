"""Bounded offline forecast observations. Never backdate acquisition or overwrite history."""
import argparse
from datetime import datetime, date, timezone, timedelta
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse
from independent_engine import load
from research_brief_html import render

SCHEMA = 'forecast-observations-v1'
METHOD = 'acquisition-bound-history-1'
UNITS = {'元': Decimal(1), '万元': Decimal(10000), '亿元': Decimal(100000000), '元/股': Decimal(1)}


def instant(value):
    if not isinstance(value, str):
        raise ValueError('时点须为含时区的ISO文字')
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError('取得/截止时点须含时区')
    return result


def validate(record):
    for key in ('id', 'entity', 'institution', 'reportId', 'metric', 'currency', 'reportVersion', 'sourceVersion', 'sourceTier'):
        if not isinstance(record.get(key), str) or not record[key].strip():
            raise ValueError('预测字段缺失：' + key)
    if record['metric'] not in ('parentNetProfit', 'revenue', 'eps') or record['currency'] != 'CNY':
        raise ValueError('本批限定明确CNY营收/归母利润/EPS')
    for key in ('publishedDate', 'forecastPeriod'):
        if date.fromisoformat(record[key]).isoformat() != record[key]:
            raise ValueError('发布日期/预测财年无效')
    if record['forecastPeriod'][5:] != '12-31':
        raise ValueError('首版限定完整财年预测')
    acquired = instant(record['acquiredAt'])
    if acquired.astimezone(timezone(timedelta(hours=8))).date() < date.fromisoformat(record['publishedDate']):
        raise ValueError('取得早于声明发布日期')
    if record.get('publishedTimePrecision') != 'date-only':
        raise ValueError('首版仅保留发布日期，不猜盘中时间')
    # Historical public availability is not inferred from the publication date.
    if record.get('knownAvailableAt') not in (None, record['acquiredAt']):
        raise ValueError('首版仅以已留存取得时点作为已知可得，不接受回填历史可得时点')
    if urlparse(record.get('source', '')).scheme != 'https':
        raise ValueError('来源须为HTTPS')
    digest = record.get('rawSourceSha256', '')
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        raise ValueError('来源摘要缺失')
    unit = record.get('unit')
    if unit not in UNITS or (record['metric'] == 'eps') != (unit == '元/股'):
        raise ValueError('预测指标与金额/每股单位不一致')
    if isinstance(record.get('value'), bool):
        raise ValueError('预测值不能为布尔值')
    value = Decimal(str(record['value']))
    if not value.is_finite():
        raise ValueError('预测值须有限')
    for key in ('scope', 'basis', 'profitAttribution', 'shareBasis'):
        if record.get(key) is not None and (not isinstance(record[key], str) or not record[key].strip()):
            raise ValueError('口径须为明确文字或未知null')
    return value * UNITS[unit]


def calculate(spec):
    if not isinstance(spec, dict):
        raise ValueError('预测档案输入须为对象')
    if spec.get('inputSchema') != SCHEMA or spec.get('methodVersion') != METHOD:
        raise ValueError('未知显式档案schema或方法版本')
    cutoff = instant(spec['asOf'])
    records = spec['records']
    if not isinstance(records, list) or not 1 <= len(records) <= 10000:
        raise ValueError('需要1至10000条明确预测观察')
    ids, eligible, excluded, groups = set(), [], [], {}
    for row in records:
        value = validate(row)
        if row['id'] in ids:
            raise ValueError('观察标识重复，不能覆盖历史')
        ids.add(row['id'])
        if instant(row['acquiredAt']) > cutoff:
            excluded.append(dict(id=row['id'], reason='取得晚于截止；不从发布日期回填可得'))
            continue
        eligible.append(row)
        key = tuple(row.get(k) for k in ('entity', 'institution', 'reportId', 'forecastPeriod', 'metric', 'currency', 'scope', 'basis', 'profitAttribution', 'shareBasis'))
        groups.setdefault(key, []).append((row, value))
    observations = []
    for members in groups.values():
        values = {value for _, value in members}
        rows = [row for row, _ in members]
        unknown = any(rows[0].get(k) is None for k in ('scope', 'basis')) or (rows[0]['metric'] == 'eps' and rows[0].get('shareBasis') is None) or (rows[0]['metric'] == 'parentNetProfit' and rows[0].get('profitAttribution') is None)
        observations.append(dict(ids=[row['id'] for row in rows], entity=rows[0]['entity'], institution=rows[0]['institution'],
                                 reportId=rows[0]['reportId'], forecastPeriod=rows[0]['forecastPeriod'], metric=rows[0]['metric'],
                                 status='source-value-conflict' if len(values) > 1 else 'repeat-observation' if len(rows) > 1 else 'single-observation',
                                 comparableBasis='unknown' if unknown else 'declared-only', acquisitions=[row['acquiredAt'] for row in rows],
                                 values=[dict(value=row['value'], unit=row['unit'], sourceVersion=row['sourceVersion']) for row in rows]))
    revisions = []
    index = {row['id']: row for row in eligible}
    for row in eligible:
        previous_id = row.get('supersedesId')
        if previous_id is None:
            continue
        previous = index.get(previous_id)
        if previous is None or not row.get('revisionEvidence'):
            revisions.append(dict(id=row['id'], status='relation-evidence-or-prior-observation-missing', difference=None))
            continue
        dimensions = ('entity', 'institution', 'forecastPeriod', 'metric', 'currency', 'scope', 'basis', 'profitAttribution', 'shareBasis')
        if any(row.get(k) != previous.get(k) for k in dimensions) or any(row.get(k) is None for k in ('scope', 'basis')) or (row['metric'] == 'parentNetProfit' and row.get('profitAttribution') is None) or (row['metric'] == 'eps' and row.get('shareBasis') is None):
            status = 'not-comparable-basis';difference = None
        elif row['reportId'] == previous['reportId']:
            status = 'same-report-source-conflict-not-analyst-revision';difference = None
        elif row['publishedDate'] <= previous['publishedDate']:
            status = 'same-day-or-reversed-order-unknown';difference = None
        else:
            status = 'declared-revision-not-original-verified';difference = str(validate(row) - validate(previous))
        revisions.append(dict(id=row['id'], priorId=previous_id, status=status, difference=difference,
                              evidence=row['revisionEvidence']))
    return dict(inputSchema=SCHEMA, methodVersion=METHOD, asOf=spec['asOf'], observations=observations, revisions=revisions,
                excluded=excluded, actualComparisonStatus='not-paired',
                conclusion='按已经留存的取得时点查历史；报告写得早，不代表我们当时已拿到。来源冲突与分析师修正分开，缺口不补。',
                limitations=['中国市场发布日期按+08:00日历日，非盘中时点；取得时点须含时区',
                             '公开网页补录不是事前冻结样本；仅已留存取得时点筛选', '同报告不同源值不自动择优，修正关联仅为输入声明',
                             '实际业绩和重述尚未原文配对，不评价预测准确率；原始研报未取得不冒充机构原文',
                             '日期精度无法区分同日发布先后，不输出全市场覆盖承诺'])


def publish(spec, archive_dir, out_dir):
    archive = Path(archive_dir);out = Path(out_dir)
    if out.exists() or out.resolve() == archive.resolve():
        raise ValueError('请使用新报告目录，历史结果不覆盖')
    # Immutable observation files; an ID's content may never be replaced.
    stored = {}
    if archive.exists():
        for path in archive.glob('observation-*.json'):
            row = load(path);validate(row)
            if row['id'] in stored:
                raise ValueError('档案中存在重复标识')
            stored[row['id']] = row
    for row in spec['records']:
        validate(row)
        if row['id'] in stored and stored[row['id']] != row:
            raise ValueError('同一观察标识内容改变，需新ID留存冲突，不能覆盖')
    combined = dict(spec, records=list(stored.values()) + [r for r in spec['records'] if r['id'] not in stored])
    result = calculate(combined)
    archive.mkdir(parents=True, exist_ok=True)
    for row in spec['records']:
        if row['id'] not in stored:
            filename = 'observation-' + hashlib.sha256(row['id'].encode()).hexdigest() + '.json'
            with (archive / filename).open('x', encoding='utf-8') as stream:
                json.dump(row, stream, ensure_ascii=False, indent=2, allow_nan=False)
    out.mkdir(parents=True)
    body = '# 机构预测留档观察\n\n' + result['conclusion'] + '\n\n本次显示' + str(len(result['observations'])) + '组预测观察；截止时点之后取得的' + str(len(result['excluded'])) + '条不纳入。\n\n'
    for row in result['observations']:
        body += '## ' + row['entity'] + '：' + row['institution'] + '\n\n预测财年' + row['forecastPeriod'] + '，指标' + row['metric'] + '。'
        body += '源值冲突，全部保留。' if row['status'] == 'source-value-conflict' else '保留已取得记录。'
        body += '口径：' + ('尚有未知，不作准确率评价。' if row['comparableBasis'] == 'unknown' else '按输入声明，未核机构原文。') + '\n\n'
        for v in row['values']:
            body += '预测值' + str(v['value']) + v['unit'] + '；来源版本' + v['sourceVersion'] + '。\n\n'
    body += '## 来源与限制\n\n'
    for row in combined['records']:
        if instant(row['acquiredAt']) <= instant(spec['asOf']):
            body += row['source'] + '；来源等级' + row['sourceTier'] + '；声明发布日期' + row['publishedDate'] + '，取得时点' + row['acquiredAt'] + '。\n\n'
    body += '\n\n'.join(result['limitations']) + '\n\n不构成投资建议。'
    for name, text in [('input.json', json.dumps(combined, ensure_ascii=False, indent=2)), ('result.json', json.dumps(result, ensure_ascii=False, indent=2)),
                       ('预测留档.md', body), ('预测留档.html', render(body, '机构预测留档观察'))]:
        (out / name).write_text(text, encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser();parser.add_argument('input');parser.add_argument('--archive-dir', required=True);parser.add_argument('--out-dir', required=True)
    args = parser.parse_args()
    try:
        publish(load(args.input), args.archive_dir, args.out_dir)
    except (ValueError, OSError, KeyError, ArithmeticError) as error:
        parser.exit(2, '未完成预测档案：' + str(error) + '\n')
