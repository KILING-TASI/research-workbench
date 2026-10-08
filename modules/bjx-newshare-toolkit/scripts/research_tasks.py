"""Persist browser research exports and record resumable, evidence-backed work."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone
import uuid

ROOT = Path(__file__).resolve().parents[1]

def now():
    return datetime.now(timezone.utc).isoformat()

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temp, path)

def task_path(folder, task_id):
    return folder / (hashlib.sha256(task_id.encode()).hexdigest() + '.json')

def import_records(folder, document):
    if document.get('type') != 'research-journal' or document.get('version') != 1:
        raise ValueError('不是研究记录导出文件')
    rows = document.get('rows')
    if not isinstance(rows, list) or len(rows) > 1000:
        raise ValueError('记录数量无效')
    ids = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id'] or row['id'] in ids:
            raise ValueError('记录ID无效或重复')
        if not isinstance(row.get('snapshot'), dict) or not isinstance(row.get('title'), str):
            raise ValueError('缺少研究标题或冻结依据')
        ids.add(row['id'])
    count = 0
    for row in rows:
        path = task_path(folder, row['id'])
        if path.exists():
            task = read(path)
            if task['sourceRecord'] != row and row not in task['importVersions']:
                previous=task['importVersions'][-1] if task['importVersions'] else task['sourceRecord']
                changed=any(previous.get(key)!=row.get(key) for key in ['snapshot','claim','invalidation'])
                task['importVersions'].append(row)
                task['researchState'] = {k: row.get(k, '') for k in ['reviewDate', 'claim', 'invalidation']}
                task['executionLog'].append({'at': now(), 'action': 'import-version', 'result': '保留首次依据，新增导入版本'})
                if changed:
                    task['status']='pending'
                    for step in task['steps']:step['status']='pending'
                    task['executionLog'].append({'at':now(),'action':'review-invalidated','result':'资料、判断或反证条件变化，旧步骤完成状态不覆盖新版本'})
                write(path, task)
            continue
        task = {'type': 'research-task', 'version': 1, 'id': row['id'], 'title': row['title'],
                'createdAt': now(), 'status': 'pending', 'sourceRecord': row, 'importVersions': [],
                'researchState': {k: row.get(k, '') for k in ['reviewDate', 'claim', 'invalidation']},
                'steps': [{'id': key, 'status': 'pending'} for key in ['核对来源与口径', '检查数据时点与缺口', '检验判断及反方证据', '记录结论与下次复查']],
                'executionLog': [], 'evidence': []}
        write(path, task)
        count += 1
    return count

def record_result(folder, task_id, step_id, result, evidence, completed=False):
    path = task_path(folder, task_id)
    task = read(path)
    step = next((s for s in task['steps'] if s['id'] == step_id), None)
    if step is None:
        raise ValueError('未知待办步骤')
    if completed and not evidence:
        raise ValueError('完成步骤必须附可复核证据')
    step['status'] = 'completed' if completed else 'pending'
    task['executionLog'].append({'at': now(), 'step': step_id, 'result': result, 'evidence': evidence, 'completed': completed})
    task['evidence'].extend(evidence)
    task['status'] = 'completed' if all(s['status'] == 'completed' for s in task['steps']) else 'pending'
    write(path, task)
    return task

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', type=Path, default=ROOT / 'research' / 'tasks')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('import'); p.add_argument('file', type=Path)
    p = sub.add_parser('create'); p.add_argument('--title', required=True); p.add_argument('--snapshot', type=Path, required=True)
    p.add_argument('--review-date', default=''); p.add_argument('--claim', default=''); p.add_argument('--invalidation', default='')
    p = sub.add_parser('due'); p.add_argument('--as-of', required=True)
    p = sub.add_parser('review'); p.add_argument('id'); p.add_argument('--changes', type=Path, required=True)
    p.add_argument('--conclusion', required=True); p.add_argument('--next-review', required=True)
    p.add_argument('--invalidation-status', choices=['yes', 'no', 'unknown'], required=True)
    sub.add_parser('list')
    p = sub.add_parser('show'); p.add_argument('id')
    p = sub.add_parser('record'); p.add_argument('id'); p.add_argument('--step', required=True)
    p.add_argument('--result', required=True); p.add_argument('--evidence', action='append', default=[]); p.add_argument('--complete', action='store_true')
    p = sub.add_parser('export'); p.add_argument('file', type=Path)
    args = parser.parse_args()
    if args.command == 'create':
        if args.review_date:
            datetime.strptime(args.review_date, '%Y-%m-%d')
        row = {'id': str(uuid.uuid4()), 'title': args.title, 'snapshot': read(args.snapshot), 'createdAt': now(),
               'status': '待核验', 'reviewDate': args.review_date, 'claim': args.claim, 'invalidation': args.invalidation, 'note': ''}
        import_records(args.store, {'type': 'research-journal', 'version': 1, 'rows': [row]})
        print(json.dumps({'taskId': row['id'], 'path': str(task_path(args.store, row['id']))}, ensure_ascii=False))
    elif args.command == 'due':
        datetime.strptime(args.as_of, '%Y-%m-%d')
        tasks = [read(p) for p in args.store.glob('*.json')]
        pending = []
        for task in tasks:
            due = task.get('researchState', task['sourceRecord']).get('reviewDate')
            if due and due <= args.as_of and task['status'] != 'completed':
                pending.append({'id': task['id'], 'title': task['title'], 'reviewDate': due})
        print(json.dumps(sorted(pending, key=lambda t: t['reviewDate']), ensure_ascii=False, indent=2))
    elif args.command == 'review':
        datetime.strptime(args.next_review, '%Y-%m-%d')
        path = task_path(args.store, args.id); task = read(path); changes = read(args.changes)
        original_hash = hashlib.sha256(json.dumps(task['sourceRecord']['snapshot'], sort_keys=True).encode()).hexdigest()
        if changes.get('type') != 'research-review' or changes.get('beforeSha256') != original_hash:
            raise ValueError('复查结果不是以本任务首次依据为起点')
        task.setdefault('reviews', []).append({'at': now(), 'changes': changes, 'conclusion': args.conclusion,
                                              'invalidationStatus': args.invalidation_status, 'evidenceFile': str(args.changes)})
        task.setdefault('researchState', {})['reviewDate'] = args.next_review
        task['status'] = 'pending'
        for step in task['steps']:step['status']='pending'
        write(path, task)
        print(json.dumps({'id': args.id, 'reviewDate': args.next_review, 'reviews': len(task['reviews'])}, ensure_ascii=False))
    elif args.command == 'import':
        print(json.dumps({'新增任务': import_records(args.store, read(args.file))}, ensure_ascii=False))
    elif args.command == 'show':
        print(json.dumps(read(task_path(args.store, args.id)), ensure_ascii=False, indent=2))
    elif args.command == 'record':
        print(json.dumps(record_result(args.store, args.id, args.step, args.result, args.evidence, args.complete), ensure_ascii=False, indent=2))
    else:
        tasks = [read(p) for p in sorted(args.store.glob('*.json'))]
        if args.command == 'export':
            write(args.file, {'type': 'research-task-archive', 'version': 1, 'tasks': tasks})
        else:
            print(json.dumps([{'id': t['id'], 'title': t['title'], 'status': t['status'], 'reviewDate': t.get('researchState', t['sourceRecord']).get('reviewDate'), 'pending': [s['id'] for s in t['steps'] if s['status'] != 'completed']} for t in tasks], ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
