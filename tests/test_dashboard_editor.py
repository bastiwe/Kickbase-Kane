import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest

import requests

from advisor_server import create_server
from features.dashboard_layout import empty_design, load_design, validate_design


def design_fixture():
    element = {'id': 'text', 'type': 'data', 'text': 'Budget: ', 'source': '/report/budget', 'url': '',
               'x': 5, 'y': 10, 'w': 90, 'h': 50, 'color': '#ffffff', 'background': '#000000',
               'backgroundOpacity': 0, 'opacity': 1, 'fontSize': 20, 'bold': True, 'radius': 0,
               'zoom': 1, 'imageY': 50, 'align': 'left', 'fit': 'contain', 'format': 'euro'}
    tile = {'id': 'budget', 'title': 'Budget', 'x': 0, 'y': 0, 'w': 4, 'h': 3,
            'color': '#102231', 'opacity': .5, 'collection': '', 'record': '', 'elements': [element]}
    layout = {'columns': 12, 'rowHeight': 32, 'gap': 12, 'tiles': [tile]}
    return {'version': 1, 'revision': 0, 'enabled': True, 'desktop': layout, 'mobile': copy.deepcopy(layout)}


class DesignValidationTests(unittest.TestCase):
    def test_repeated_sections_roundtrip_and_never_bind_concrete_players(self):
        design = design_fixture()
        tile = design['desktop']['tiles'][0]
        tile.update(section='roster', cardColumns=3, cardHeight=240, cardGap=12,
                    cardColor='#112233', cardOpacity=.7, collection='/report/players', record='id:7')
        clean = validate_design(design)
        self.assertEqual(clean['desktop']['tiles'][0]['section'], 'roster')
        self.assertEqual(clean['desktop']['tiles'][0]['cardColumns'], 3)
        self.assertEqual(clean['desktop']['tiles'][0]['collection'], '')
        self.assertEqual(clean['desktop']['tiles'][0]['record'], '')
        self.assertEqual(validate_design(clean), clean)

    def test_duplicate_sections_and_invalid_player_grids_are_rejected(self):
        base = design_fixture()
        base['desktop']['tiles'][0].update(section='market', cardColumns=2, cardHeight=240,
                                          cardGap=12, cardColor='#112233', cardOpacity=1)
        for key, value in [('section', 'unknown'), ('cardColumns', 0), ('cardColumns', 2.5),
                           ('cardHeight', 2000), ('cardGap', -1), ('cardOpacity', 5)]:
            with self.subTest(key=key, value=value):
                design = copy.deepcopy(base)
                design['desktop']['tiles'][0][key] = value
                with self.assertRaises(ValueError):
                    validate_design(design)
        tile = copy.deepcopy(base['desktop']['tiles'][0])
        tile['id'] = 'another'
        base['desktop']['tiles'].append(tile)
        with self.assertRaises(ValueError):
            validate_design(base)

    def test_roundtrip_preserves_separate_views_and_missing_sources(self):
        design = design_fixture()
        design['mobile']['columns'] = 4
        design['mobile']['tiles'][0]['elements'][0]['source'] = '/api/notLoadedYet/value'
        self.assertEqual(validate_design(design), design)
        self.assertEqual(validate_design(empty_design()), empty_design())

    def test_rejects_unsafe_or_unbounded_designs(self):
        changes = [lambda d: d['desktop'].update(columns=0),
                   lambda d: d['desktop'].update(rowHeight=float('nan')),
                   lambda d: d['desktop']['tiles'][0].update(x=11),
                   lambda d: d['desktop']['tiles'][0].update(color='red;position:fixed'),
                   lambda d: d['desktop']['tiles'][0]['elements'][0].update(type='html'),
                   lambda d: d['desktop']['tiles'][0]['elements'][0].update(url='javascript:alert(1)'),
                   lambda d: d['desktop']['tiles'][0]['elements'][0].update(url='data:text/html;base64,abc'),
                   lambda d: d['desktop']['tiles'][0]['elements'][0].update(x=99),
                   lambda d: d['desktop']['tiles'][0]['elements'][0].update(opacity=2),
                   lambda d: d['desktop']['tiles'][0]['elements'].append(copy.deepcopy(d['desktop']['tiles'][0]['elements'][0])),
                   lambda d: d['desktop']['tiles'].append(copy.deepcopy(d['desktop']['tiles'][0])),
                   lambda d: d['desktop']['tiles'][0]['elements'][0].update(url='data:image/png;base64,'+'a'*250000)]
        for change in changes:
            with self.subTest(change=change):
                design = design_fixture()
                change(design)
                with self.assertRaises(ValueError):
                    validate_design(design)

    def test_empty_and_corrupt_storage_falls_back_without_losing_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'layout.json'
            self.assertEqual(load_design(path), empty_design())
            for content in ['not json', 'null', '[]', '{"version":1}']:
                path.write_text(content, encoding='utf-8')
                self.assertEqual(load_design(path), empty_design())


class EditorApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.report = {'players': [{'id': '7', 'name': '</script><script>window.bad=true</script>', 'owned': True}],
                       'budget': 12345, 'generated': 'Test'}
        self.server = create_server(0, self.report)
        self.server.layout_path = Path(self.tmp.name) / 'layout.json'
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.headers = {'Origin': self.server.origin, 'X-Advisor-Token': self.server.csrf}

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def post(self, design, path='/api/dashboard-layout'):
        return requests.post(self.server.origin + path, json=design, headers=self.headers, timeout=5)

    def test_editor_and_assets_are_served_without_script_injection(self):
        response = requests.get(self.server.origin + '/editor', timeout=5)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('</script><script>window.bad=true', response.text)
        for asset in ['dashboard_layout.js', 'dashboard_editor.js', 'dashboard_editor.css', 'dashboard_preview.js']:
            self.assertEqual(requests.get(self.server.origin + '/' + asset, timeout=5).status_code, 200)
        self.assertEqual(requests.get(self.server.origin + '/api/dashboard-data', timeout=5).json(), self.report)

    def test_preview_is_real_dashboard_and_can_only_embed_locally(self):
        response = requests.get(self.server.origin + '/preview', timeout=5)
        self.assertEqual(response.status_code, 200)
        self.assertIn('"preview": true', response.text)
        self.assertIn('id="metric-budget"', response.text)
        self.assertIn('id="custom-dashboard"', response.text)
        self.assertNotIn('</script><script>window.bad=true', response.text)
        self.assertIn("frame-ancestors 'self'", response.headers['Content-Security-Policy'])
        regular = requests.get(self.server.origin + '/editor', timeout=5)
        self.assertIn("frame-ancestors 'none'", regular.headers['Content-Security-Policy'])
        self.assertFalse(self.server.layout_path.exists())

    def test_save_persists_both_views_and_conflicts_do_not_overwrite(self):
        design = design_fixture()
        design['mobile']['columns'] = 4
        response = self.post(design)
        self.assertEqual(response.status_code, 200, response.text)
        saved = response.json()
        self.assertEqual(saved['revision'], 1)
        self.assertEqual(load_design(self.server.layout_path), saved)
        # A new server reads the same /data design, independently of its report and session.
        restarted = create_server(0, self.report)
        try:
            restarted.layout_path = self.server.layout_path
            self.assertEqual(load_design(restarted.layout_path), saved)
        finally:
            restarted.server_close()
        self.assertEqual(self.post(design).status_code, 409)
        self.assertEqual(load_design(self.server.layout_path), saved)
        saved['enabled'] = False
        self.assertEqual(self.post(saved).json()['revision'], 2)

    def test_validation_import_does_not_write_and_invalid_save_keeps_previous(self):
        design = design_fixture()
        self.assertEqual(self.post(design, '/api/dashboard-layout/validate').status_code, 200)
        self.assertFalse(self.server.layout_path.exists())
        saved = self.post(design).json()
        invalid = copy.deepcopy(saved)
        invalid['desktop']['tiles'][0]['w'] = 24
        self.assertEqual(self.post(invalid).status_code, 400)
        self.assertEqual(load_design(self.server.layout_path), saved)

    def test_layout_writes_require_csrf_and_valid_origin(self):
        for headers in [{}, {'Origin': self.server.origin}, {**self.headers, 'Origin': 'https://example.com'}]:
            response = requests.post(self.server.origin + '/api/dashboard-layout', json=design_fixture(), headers=headers, timeout=5)
            self.assertEqual(response.status_code, 403)
        self.assertFalse(self.server.layout_path.exists())


if __name__ == '__main__':
    unittest.main()
