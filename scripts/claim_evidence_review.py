# SPDX-License-Identifier: MIT
"""Bind supplied claims to declared evidence without certifying their truth."""
from evidence_status_review import review as availability
from review_io import cli

LABELS = {'conflicting': '支持与反对材料并存，不能按票数判真', 'declared-support': '有声明直接支持材料，仍需核原文',
          'declared-counterevidence': '有声明反对材料，仍需核原文', 'partial-only': '只有局部支持，不能推广至整条消息',
          'context-only': '只有背景资料，不能证明消息', 'insufficient': '缺少可纳入的直接证据'}


def review(spec):
    if not isinstance(spec, dict) or spec.get('inputSchema') != 'claim-evidence/1' or set(spec) != {'inputSchema', 'evidence', 'claims'}:
        raise ValueError('须为claim-evidence/1，提供资料状态与逐条主张')
    evidence = availability(spec['evidence']); records = {r['id']: r for r in evidence['records']}
    claims = spec['claims']
    if not isinstance(claims, list) or not 1 <= len(claims) <= 100: raise ValueError('需1至100条主张')
    rows = []; ids = set()
    for claim in claims:
        if not isinstance(claim, dict) or set(claim) != {'id', 'text', 'subjectId', 'referencePeriod', 'links'}:
            raise ValueError('主张须明确ID、文字、对象、期间及证据关联')
        if any(not isinstance(claim[k], str) or not claim[k].strip() for k in ('id', 'text', 'subjectId', 'referencePeriod')) or claim['id'] in ids:
            raise ValueError('主张ID须唯一，对象、期间及文字不能为空')
        ids.add(claim['id'])
        if not isinstance(claim['links'], list) or len(claim['links']) > 100: raise ValueError('关联须为列表，最多100项')
        admitted = []; excluded = []; used = set()
        for link in claim['links']:
            if not isinstance(link, dict) or set(link) != {'evidenceId', 'relation', 'rationale'}: raise ValueError('关联须声明证据ID、关系与逐条理由')
            eid = link['evidenceId']
            if not isinstance(eid, str) or eid not in records or eid in used: raise ValueError('关联资料不存在或重复')
            used.add(eid); record = records[eid]
            if link['relation'] not in {'supports', 'contradicts', 'partial', 'context'} or not isinstance(link['rationale'], str) or not link['rationale'].strip():
                raise ValueError('关联关系无效或理由缺失')
            reason = None
            if record['reviewStatus'] != 'available': reason = record['reviewStatus']
            elif record.get('subjectId') != claim['subjectId']: reason = 'subject-mismatch-or-unknown'
            elif record.get('referencePeriod') != claim['referencePeriod']: reason = 'period-mismatch-or-unknown'
            elif not isinstance(record.get('excerpt'), str) or not record['excerpt'].strip(): reason = 'excerpt-missing'
            elif link['relation'] in {'supports', 'contradicts'} and record['valueType'] != 'disclosed': reason = 'estimate-or-proxy-not-direct-evidence'
            binding = dict(link, source=record.get('source'), locator=record.get('locator'), sourceVersion=record.get('sourceVersion'),
                           rawSourceSha256=record.get('rawSourceSha256'), excerpt=record.get('excerpt'), originalVerified=False)
            if reason: excluded.append(dict(binding, exclusion=reason))
            else: admitted.append(binding)
        roles = {r['relation'] for r in admitted}
        status = 'conflicting' if {'supports', 'contradicts'} <= roles else 'declared-support' if 'supports' in roles else 'declared-counterevidence' if 'contradicts' in roles else 'partial-only' if 'partial' in roles else 'context-only' if roles else 'insufficient'
        groups = {}
        for record in admitted: groups.setdefault(record['rawSourceSha256'], []).append(record['evidenceId'])
        rows.append(dict(claim, status=status, admitted=admitted, excluded=excluded, sourceArtifactGroups=list(groups.values()),
                         independenceVerified=False, originalVerified=False, judgment=LABELS[status]))
    issues = [r for r in rows if r['status'] != 'declared-support']
    return {'methodVersion': 'claim-evidence/1', 'question': evidence['question'], 'status': 'needs-review', 'records': rows,
            'evidenceReview': evidence, 'conclusion': ('教学资料，非真实消息核验。' if spec['evidence'].get('sampleType') == 'teaching' else '') + f'{len(rows)}条主张中，{len(issues)}条缺少单向直接支持或存在冲突；即使有支持材料，本流程也未认证消息为真。',
            'humanRows': [[r['text'], r['judgment'] + f'；纳入{len(r["admitted"])}项、排除{len(r["excluded"])}项'] for r in rows],
            'limitations': ['资料关系由输入者逐条声明，程序检查时点、对象、期间和绑定；不自动理解原文含义',
                            '原文摘录和文件摘要均为声明，未在本次读取原始文件或认证发布机构',
                            '同一文件摘要的转载合并显示；不同摘要也不证明来源独立，不能数票或输出可信概率',
                            '背景、估算、代理和局部支持不能证明整条消息；更正版本须重新提供资料并人工确认',
                            '消息成立不等于价格已低估、收益确定或可以交易；失败和未知不补成否定事实']}


if __name__ == '__main__': raise SystemExit(cli({'review': review}, '消息与证据逐条核对'))
