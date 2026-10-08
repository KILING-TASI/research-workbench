"""Title-based version leads, never a claim that a correction replaces a fact."""
import re

def version_review(items):
    groups = {}
    for item in items:
        title = re.sub(r'\s+|<[^>]+>', '', item.get('title', ''))
        family = next((x for x in ['发行结果', '发行公告', '招股说明书', '上市公告'] if x in title), None)
        changed = any(x in title for x in ['更正', '修订', '补充', '更新', '取消', '撤回'])
        if not family and not changed:
            continue
        groups.setdefault(family or '未明确关联文件', []).append({
            'title': item.get('title'), 'url': item.get('url'), 'date': item.get('date'),
            'changeLead': changed})
    reviews = []
    for family, entries in groups.items():
        entries.sort(key=lambda x: (x.get('date') or '', x.get('url') or ''))
        if any(x['changeLead'] for x in entries):
            reviews.append({'family': family, 'documents': entries,
                'status': 'body-comparison-required', 'supersessionConfirmed': False})
    return {'status': 'needs-body-review' if reviews else 'no-change-title-detected',
            'groups': reviews, 'scope': 'Cached title leads only; absence is not proof of no correction'}
