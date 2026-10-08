import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from build_bjx_workbench import main as build
from update_delivery_candidate import main as update
from delivery_preflight import inspect


class PortableBuild(unittest.TestCase):
    def files(self, root):
        source = root / 'source.json'
        source.write_text(json.dumps({'source': 'teaching-fixture', 'fetchedAt': '2026-10-03', 'records': []}), 'utf-8')
        overlay = root / 'overlay.json';overlay.write_text('{"records":{}}', 'utf-8')
        template = root / 'template.html'
        template.write_text('<script id="dataset" type="application/json">{"private":"OLD"}</script>', 'utf-8')
        return source, overlay, template

    def test_build_without_model_or_author_calendar(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source,overlay,template=self.files(root);out=root/'result.html'
            with patch('sys.argv',['build','--data',str(source),'--overlays',str(overlay),'--template',str(template),'--out',str(out)]):build()
            result=out.read_text('utf-8');self.assertNotIn('OLD',result)
            data=json.loads(re.search(r'json">(.*?)</script>',result).group(1))
            self.assertFalse(data['historicalModelAvailable']);self.assertNotIn('bseTradingCalendar',data)

    def test_explicit_missing_model_not_silently_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source,overlay,template=self.files(root)
            with patch('sys.argv',['build','--data',str(source),'--overlays',str(overlay),'--template',str(template),'--model',str(root/'missing.json'),'--out',str(root/'out.html')]):
                with self.assertRaises(FileNotFoundError):build()
            self.assertFalse((root/'out.html').exists())

    def test_explicit_calendar_embedded(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source,overlay,template=self.files(root);calendar=root/'calendar.json';calendar.write_text('{"year":2026,"closedRanges":[],"sourceUrl":"teaching"}', 'utf-8')
            with patch('sys.argv',['build','--data',str(source),'--overlays',str(overlay),'--template',str(template),'--bse-calendar',str(calendar),'--out',str(root/'out.html')]):build()
            self.assertIn('"sourceUrl": "teaching"',(root/'out.html').read_text('utf-8'))

    def test_preflight_override_uses_user_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source,_,_=self.files(root)
            result=inspect(root,'historical-cash',{'assets/data.json':source})
            self.assertNotIn('assets/data.json',result['missingResources'])
            self.assertIn('assets/bse-trading-calendar-2026.json',result['missingResources'])

    def test_portable_template_has_no_cached_records(self):
        template=Path(__file__).resolve().parents[1]/'assets/bjx-panel.template.html'
        text=template.read_text('utf-8')
        entries=re.findall(r'<script id="dataset" type="application/json">(.*?)</script>',text,re.S)
        self.assertEqual(len(entries),1)
        data=json.loads(entries[0]);self.assertEqual(data['records'],[]);self.assertEqual(data['annualRecords'],[])
        self.assertIsNone(data['fetchedAt']);self.assertFalse(data['historicalModelAvailable'])

    def test_update_routes_explicit_user_inputs(self):
        import subprocess
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source,overlay,template=self.files(root);out=root/'new'
            with patch('sys.argv',['update','--previous',str(source),'--overlays',str(overlay),'--template',str(template),'--original-limit','0','--out-dir',str(out)]),patch('update_delivery_candidate.inspect_resources',return_value={'missingResources':[]}) as check,patch('update_delivery_candidate.subprocess.run',return_value=subprocess.CompletedProcess([],1,'','test failure')) as run:
                with self.assertRaises(SystemExit):update()
            self.assertEqual(check.call_args.args[2]['assets/bjx-panel.html'],template)
            self.assertIn(str(source),run.call_args.args[0])
            self.assertFalse(json.loads((out/'update-report.json').read_text('utf-8'))['liveFilesOverwritten'])
