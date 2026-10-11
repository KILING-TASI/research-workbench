# SPDX-License-Identifier: MIT
"""Describe supplied evidence availability without confusing it with verification."""
from datetime import date
from review_io import cli, day, evidence, instant

LABELS = {'available':'资料已取得，原文未自动核实', 'empty':'来源返回空资料', 'failed':'取数失败', 'unauthorized':'缺少授权', 'stale':'超过声明的新鲜度窗口', 'after-cutoff':'截止后资料，未纳入', 'missing':'未提供资料'}


def review(spec):
    if spec.get('inputSchema') != 'evidence-status/1':
        raise ValueError('输入须为 evidence-status/1')
    if not isinstance(spec.get('question'), str) or not spec['question'].strip():
        raise ValueError('须明确研究问题')
    as_of = day(spec['asOfDate'])
    if instant(spec['asOf']).date() != as_of:
        raise ValueError('报告截止日期与截止时间须一致')
    limit = spec['maxAgeDays']
    if type(limit) is not int or limit < 0:
        raise ValueError('新鲜度窗口须为非负天数，由研究问题指定')
    rows = []; ids = set()
    for row in spec['records']:
        if not isinstance(row.get('id'), str) or row['id'] in ids:
            raise ValueError('资料ID缺失或重复')
        ids.add(row['id'])
        status = row['status']
        if status not in {'available','empty','failed','unauthorized','missing'}:
            raise ValueError('资料状态无效')
        if not row.get('reason'):
            raise ValueError('每项资料须注明状态原因')
        if status == 'available':
            if not evidence(row, spec['asOf']):
                status = 'after-cutoff'
            observed = day(row['dataDate'])
            if observed > as_of:
                status = 'after-cutoff'
            elif status != 'after-cutoff' and (as_of-observed).days > limit:
                status = 'stale'
            if row.get('valueType') not in {'disclosed','estimated','proxy'}:
                raise ValueError('数值类型须为披露、估算或代理')
        rows.append(dict(row, reviewStatus=status, sourceVerified=False))
    gaps = [r for r in rows if r['reviewStatus'] != 'available']
    return {'methodVersion':'evidence-status/1', 'question':spec['question'], 'conclusion':f"本次 {len(rows)} 项资料中，{len(gaps)} 项存在缺口或时点限制。资料状态完整不代表问题已得到可靠答案。", 'status':'partial' if gaps or not rows else 'ready-for-review', 'records':rows, 'humanRows':[[r['id'], LABELS[r['reviewStatus']]+'；'+r['reason']] for r in rows], 'limitations':['不联网重试、不认证原文；摘要只绑定声明资料','新鲜度窗口由输入声明，不是统一投资标准','失败、空表、未授权和未知不补成零；截止后资料不支持历史判断']}


if __name__ == '__main__':
    raise SystemExit(cli({'review':review}, '研究问题与资料状态'))
