import base64
from concurrent.futures import ThreadPoolExecutor
import copy
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import app
from check_project import check_project


class StudioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        assets = self.root / 'assets'
        assets.mkdir()
        (assets / 'icon.rgba').write_bytes(bytes([10, 20, 30, 255]) * 1600)
        self.library = assets / 'library.json'
        self.library.write_text(json.dumps(dict(films=[dict(uid=1, name='Film One', category='kodak', author='Author', icon='assets/icon.rgba'), dict(uid=2, name='Film Two', category='fujifilm', icon='assets/icon.rgba')], defaults=[1] * 6)))
        self.studio = app.Studio(self.library, self.root / 'data')
        self.project = self.studio.read()

    def test_save_and_reopen_keeps_names_selection_slots_and_icon(self):
        icon = 'data:image/png;base64,' + base64.b64encode(app.rgba_png(bytes([255, 0, 0, 255]) * 1600)).decode()
        self.project.update(selected=[2], slots=[2] * 6, overrides={'2': {'name': 'New Film', 'category': 'other', 'icon': icon, 'notes': '适合晴天、白平衡5500K\n第二行 ☀️'}})
        result = self.studio.save(self.project)
        reopened = app.Studio(self.library, self.root / 'data').read()
        self.assertEqual(result, reopened)
        self.assertEqual(result['revision'], 1)
        self.assertEqual(self.studio.films[1]['name'], 'Film Two')

    def test_custom_icon_design_round_trips_and_requires_valid_settings(self):
        icon = 'data:image/png;base64,' + base64.b64encode(app.rgba_png(bytes([255, 0, 0, 255]) * 1600)).decode()
        design = dict(brand='KODAK', small='', main='5219N', topInk='#882d24',
                      topFill='#fac744', smallInk='#ffffff', mainInk='#ffffff',
                      bodyFill='#242824', divider=True, dividerFill='#eeeeee',
                      strip=True, stripFill='#6b507f')
        self.project['overrides']['1'] = dict(icon=icon, icon_design=design)
        self.assertEqual(self.studio.save(self.project), self.studio.read())
        for bad in (dict(design, small='中文'), dict(design, brand='X' * 11),
                    dict(design, strip='true'), dict(design, mainInk='red')):
            with self.subTest(bad=bad), self.assertRaises(app.ProjectError):
                self.studio.validate(dict(self.project, overrides={'1': dict(icon=icon, icon_design=bad)}))
        with self.assertRaises(app.ProjectError):
            self.studio.validate(dict(self.project, overrides={'1': dict(icon_design=design)}))

    def test_source_files_are_unchanged(self):
        before = {p: p.read_bytes() for p in (self.root / 'assets').rglob('*') if p.is_file()}
        self.studio.save(self.project)
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_unchecked_assigned_film_is_rejected(self):
        self.project['selected'] = [2]
        with self.assertRaisesRegex(app.ProjectError, '六槽'):
            self.studio.save(self.project)
        self.assertFalse(self.studio.project_path.exists())

    def test_unknown_duplicate_boolean_and_empty_selection_rejected(self):
        for selected in ([1, 999], [1, 1], [True, 2], []):
            with self.subTest(selected=selected):
                project = dict(self.project, selected=selected)
                with self.assertRaises(app.ProjectError):
                    self.studio.save(project)

    def test_invalid_metadata_and_images_rejected(self):
        for values in ({'name': ''}, {'name': '中文'}, {'name': ' name '}, {'name': 'x' * 33}, {'category': 'unknown'}, {'icon': 'data:image/png;base64,AAAA'}, {'addresses': [0]}, {'notes': 1}, {'notes': '字' * 4001}, {'notes': '\ud800'}):
            with self.subTest(values=values):
                project = dict(self.project, overrides={'1': values})
                with self.assertRaises(app.ProjectError):
                    self.studio.save(project)

    def test_stale_save_and_parallel_save_cannot_overwrite(self):
        def save():
            try:
                return self.studio.save(copy.deepcopy(self.project))['revision']
            except app.ProjectError as error:
                return error.status
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda _: save(), range(2)))
        self.assertEqual(sorted(results), [1, 409])
        self.assertEqual(self.studio.read()['revision'], 1)

    def test_failed_replace_keeps_previous_valid_file(self):
        saved = self.studio.save(self.project)
        before = self.studio.project_path.read_bytes()
        with patch.object(app.os, 'replace', side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):
                self.studio.save(saved)
        self.assertEqual(self.studio.project_path.read_bytes(), before)
        self.assertEqual(list(self.studio.data_dir.glob('.project-*')), [])

    def test_wrong_library_and_corrupt_saved_file_are_preserved(self):
        self.project['library_id'] = 'wrong'
        with self.assertRaises(app.ProjectError):
            self.studio.save(self.project)
        self.studio.data_dir.mkdir()
        self.studio.project_path.write_text('broken')
        with self.assertRaises(app.ProjectError):
            self.studio.read()
        self.assertEqual(self.studio.project_path.read_text(), 'broken')

    def test_http_normal_entry_and_origin_protection(self):
        server = app.make_server(self.studio, 0)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        def call(method, path, body=None, extra=None):
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port)
            self.addCleanup(connection.close)
            headers = {'Content-Type': 'application/json', 'X-GRSlot-Client': 'studio-lite'}
            headers.update(extra or {})
            connection.request(method, path, json.dumps(body) if body is not None else None, headers)
            response = connection.getresponse()
            return response.status, response.read()
        status, body = call('GET', '/api/project')
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(body)['films']), 2)
        self.assertEqual(call('GET', '/api/icon/1')[0], 200)
        self.assertEqual(call('GET', '/../../app.py')[0], 404)
        self.assertEqual(call('POST', '/api/project', self.project, {'Origin': 'https://example.com'})[0], 400)
        self.assertFalse(self.studio.project_path.exists())
        self.assertEqual(call('POST', '/api/project', self.project)[0], 200)
        self.assertEqual(call('POST', '/api/project', self.project)[0], 409)


class AgentHandoffTests(unittest.TestCase):
    @patch("check_project.inspect_firmware", return_value={"status": "PASS_OFFICIAL_INPUT_ONLY"})
    def test_saved_project_is_read_without_modification(self, inspect):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            studio = app.Studio(app.DEFAULT_LIBRARY, root)
            project = studio.read()
            project["selected"] = project["slots"][:]
            project["slots"].reverse()
            uid = project["selected"][0]
            project["overrides"][str(uid)] = {"notes": "5500K，适合晴天街拍"}
            studio.save(project)
            original = studio.project_path.read_bytes()
            receipt = check_project(studio.project_path, root)
            self.assertEqual(receipt["slots"], project["slots"])
            self.assertEqual(receipt["selected"][0]["notes"], "5500K，适合晴天街拍")
            self.assertFalse(receipt["firmware_generated"])
            self.assertEqual(studio.project_path.read_bytes(), original)
            inspect.assert_called_once_with(root / "fwdc239b.bin")

    def test_wrong_library_is_rejected_before_firmware_access(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            studio = app.Studio(app.DEFAULT_LIBRARY, root)
            invalid = studio.read()
            invalid["library_id"] = "0" * 64
            studio.project_path.write_text(json.dumps(invalid))
            with self.assertRaisesRegex(ValueError, "胶片库不匹配"):
                check_project(studio.project_path, root / "missing.bin")


if __name__ == '__main__':
    unittest.main()
