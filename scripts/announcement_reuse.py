"""Read one saved BJX candidate sidecar; not a cross-repository standard."""
import argparse
import copy
import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path

METHOD = 'saved-bjx-result-selected-fields-1'
FIELDS = ('online_issue_shares', 'effective_subscription_shares', 'online_allocation_rate')


def review(sidecar, source_file, *, prospective=False):
    if sidecar.get('schema') != 'bjx-announcement-sidecar.v1':
        raise ValueError('Unsupported candidate sidecar schema')
    if sidecar.get('status') != 'candidate_not_cross_repository_standard':
        raise ValueError('Candidate scope declaration missing')
    native = sidecar['native_payload']
    result = native['documents']['result']
    if sidecar['source_version']['announcement_number'] != result['announcement_number']:
        raise ValueError('Sidecar and native source version conflict')
    if sidecar['document_id'] != f"BSE:{native['security']}:{result['announcement_number']}":
        raise ValueError('Document identity conflict')
    if sidecar['official_url'] != result['url'] or sidecar['publisher'] != native['issuer_name']:
        raise ValueError('Publisher or source URL conflict')
    for key, native_key in (('body_date', 'body_date'), ('url_path_date', 'file_path_date'),
                            ('retrieved_at', 'retrieved_at')):
        if sidecar['times'][key]['value'] != result[native_key]:
            raise ValueError('Sidecar and native time conflict')
    for key in ('published_at', 'historical_available_at'):
        if sidecar['times'][key].get('value') is not None:
            raise ValueError('This sample has no certified public availability clock')
        if not sidecar['times'][key].get('reason'):
            raise ValueError('Unknown publication/availability time requires a reason')
    available = sidecar['times']['historical_available_at']
    if available.get('value') is None and not available.get('reason'):
        raise ValueError('Unknown historical availability requires a reason')
    if prospective:
        raise ValueError('Prospective use unsupported; historical availability is not certified')
    blob = Path(source_file).read_bytes()
    digest = hashlib.sha256(blob).hexdigest()
    if digest != sidecar['sha256'] or digest != result['sha256'] or not blob.startswith(b'%PDF'):
        raise ValueError('Original file digest mismatch')
    import pdfplumber
    evidence = []
    with pdfplumber.open(source_file) as doc:
        front = re.sub(r'\s+', '', ''.join(page.extract_text() or '' for page in doc.pages[:2]))
        for token in (native['security'], sidecar['publisher'], result['announcement_number']):
            if re.sub(r'\s+', '', token) not in front:
                raise ValueError('Selected original identity not found')
        for name in FIELDS:
            field = native['fields'][name]
            if field['source_id'] != 'result' or type(field['page']) is not int or not 1 <= field['page'] <= len(doc.pages):
                raise ValueError('Selected field source/page mismatch')
            anchor = field['text_anchor']
            text = re.sub(r'\s+', '', doc.pages[field['page'] - 1].extract_text() or '')
            if anchor not in text:
                raise ValueError('Selected text anchor not found')
            if not re.fullmatch(r'[0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?%?', anchor):
                raise ValueError('Selected numeric anchor invalid')
            value = Decimal(anchor.rstrip('%').replace(',', ''))
            if name == 'online_allocation_rate':
                if not anchor.endswith('%') or field['unit'] != 'fraction':
                    raise ValueError('Selected rate unit mismatch')
                value /= 100
            elif field['unit'] != 'shares' or anchor.endswith('%'):
                raise ValueError('Selected share unit mismatch')
            if value != Decimal(str(field['value'])):
                raise ValueError('Selected value disagrees with original token')
            evidence.append({'field': name, 'physicalPage': field['page'], 'anchor': anchor,
                             'value': field['value'], 'unit': field['unit']})
    return {'consumer': 'research-workbench', 'methodVersion': METHOD,
            'sourceSha256': digest, 'status': 'three-selected-fields-text-verified',
            'parser': 'pdfplumber', 'evidence': evidence,
            'historicalAvailableAt': copy.deepcopy(available),
            'sourceRecord': copy.deepcopy(sidecar),
            'limitations': ['No download or new visual certification',
                            'Not full-document, complete-version or account eligibility verification',
                            'Body/URL dates do not establish first public availability']}


def main():
    from collection_validation import unique_pairs, reject_constant
    parser = argparse.ArgumentParser()
    parser.add_argument('sidecar')
    parser.add_argument('--source-file', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    record = json.loads(Path(args.sidecar).read_text('utf-8'), object_pairs_hook=unique_pairs,
                        parse_constant=reject_constant)
    output = review(record, args.source_file)
    output['sidecarFileSha256'] = hashlib.sha256(Path(args.sidecar).read_bytes()).hexdigest()
    with Path(args.out).open('x', encoding='utf-8') as stream:
        json.dump(output, stream, ensure_ascii=False, indent=2, allow_nan=False)


if __name__ == '__main__':
    main()
