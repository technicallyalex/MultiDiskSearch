import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import unittest
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
from unittest.mock import Mock, patch
from PySide6.QtCore import QUrl, QEventLoop, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtNetwork import QNetworkReply
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from qt_app import Controller, load_fonts, brand_icon


class QuickTests(unittest.TestCase):
    def test_update_check_compares_versions_and_uses_repository_link(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp:
            controller = Controller(Mock(), Path(temp) / 'settings.json')
            for tag, status, suffix in (
                ('v1.10.0', '1.10.0 is available.', '/tag/v1.10.0'),
                ('v1.0.1', 'No newer release available.', ''),
                ('v1.2.0-rc.1', 'Could not read the release information from GitHub.', ''),
            ):
                with self.subTest(tag=tag), patch('qt_app.VERSION', '1.2.0'):
                    reply = Mock()
                    reply.error.return_value = QNetworkReply.NetworkError.NoError
                    reply.readAll.return_value = (
                        f'{{"tag_name":"{tag}","draft":false,"prerelease":false,'
                        '"html_url":"https://example.com"}'
                    ).encode()
                    controller._update_url = ''
                    controller._update_reply = reply
                    controller.finishUpdateCheck()
                    self.assertEqual(controller.updateStatus, status)
                    expected = 'https://github.com/technicallyalex/MultiDiskSearch/releases' + suffix if suffix else ''
                    self.assertEqual(controller.updateUrl, expected)
                    self.assertFalse(controller.updateChecking)

    def test_legacy_worker_settings_default_to_auto_and_new_overrides_persist(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp:
            config = Path(temp) / 'settings.json'
            config.write_text('{"workers": 3}', encoding='utf-8')
            controller = Controller(Mock(), config)
            self.assertEqual(controller.maxWorkers, 0)
            controller.configureSearch('project', 'direct', 2)
            self.assertEqual(Controller(Mock(), config).maxWorkers, 2)

    def test_index_first_options_size_and_per_filename_review(self):
        app=QGuiApplication.instance() or QGuiApplication([])
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp:
            config=Path(temp)/'settings.json'
            controller=Controller(Mock(),config)
            controller.configureSearch('timeline','index_first',3)
            self.assertEqual(Controller(Mock(),config).searchMethod,'index_first')
            self.assertEqual(controller.indexDiskSize,'0 B')
            rows=[dict(key=str(i),name=name,old='X:/'+name,target='',status='Searching',thumbnail='',previewLabel='')
                  for i,name in enumerate(('cached.mov','new.mov'))]
            controller.receive('rows',rows)
            controller.receive('matched',({'cached.mov':{'E:/cached.mov'},'new.mov':{'E:/new.mov'}},
                ['Cached snapshot requires review'],False,{'new.mov'}))
            self.assertEqual(controller.rows[0]['target'],'')
            self.assertEqual(controller.rows[1]['target'],'E:/new.mov')
            self.assertEqual(controller.readyCount,1)

    def test_indexed_controller_search_requires_review_and_persists_options(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp:
            root = Path(temp) / 'Footage'
            root.mkdir()
            target = root / 'clip.mov'
            target.touch()
            config = Path(temp) / 'settings.json'
            bridge = Mock()
            def request(command, **kwargs):
                if command == 'inventory':
                    return {'timeline':'Edit', 'rows':[dict(key='0',name='Clip',old='X:/missing/clip.mov',target='',status='Searching',thumbnail='',previewLabel='No preview available')]}
                return True
            bridge.request.side_effect = request
            controller = Controller(bridge,config)
            def wait():
                loop=QEventLoop()
                controller.changed.connect(lambda: loop.quit() if not controller.busy else None)
                QTimer.singleShot(5000,loop.quit)
                loop.exec()
                for worker in list(controller.workers):
                    worker.wait(1000)
                app.processEvents()
                self.assertFalse(controller.busy)
            controller.addLocation(QUrl.fromLocalFile(str(root)))
            wait()
            self.assertIn('1 files',controller.roots[0]['indexDetail'])
            controller.configureSearch('timeline','index',2)
            with patch('qt_app.file_thumbnail',return_value=''):
                controller.find()
                wait()
                self.assertEqual(controller.timelineName,'Edit')
                self.assertEqual(controller.readyCount,0)
                self.assertEqual(controller.rows[0]['status'],'Review source')
                controller.chooseCandidate(0,str(target))
                wait()
                self.assertEqual(controller.readyCount,1)
            reopened=Controller(bridge,config)
            self.assertEqual((reopened.searchScope,reopened.searchMethod,reopened.maxWorkers),('timeline','index',2))
            self.assertIn('1 files',reopened.roots[0]['indexDetail'])

    def test_approved_brand_icon_renders(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        icon = brand_icon()
        self.assertFalse(icon.isNull())
        self.assertFalse(icon.pixmap(32, 32).isNull())
        self.assertFalse(icon.pixmap(256, 256).isNull())

    def test_incomplete_search_requires_review_and_failure_keeps_retry(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp:
            controller = Controller(Mock(), Path(temp) / 'settings.json')
            original = dict(key='0', name='Clip', old='X:/clip.mov', target='', status='Searching', thumbnail='', previewLabel='No preview available')
            controller.receive('rows', [original])
            controller.receive('matched', ({'clip.mov':{'Z:/clip.mov'}}, ['Unavailable: Y:/'], False))
            self.assertEqual(controller.rows[0]['status'], 'Review source')
            self.assertEqual(controller.readyCount, 0)
            self.assertEqual(original['status'], 'Searching')
            controller.rows[0]['target'] = 'Z:/clip.mov'
            controller.receive('relinked', (0, 'Source disappeared'))
            self.assertEqual(controller.rows[0]['target'], 'Z:/clip.mov')
            controller.rows.append(dict(original, key='1', name='Other'))
            controller.setFilter('Other', 'All clips')
            self.assertEqual(controller.displayRows[0]['sourceIndex'], 1)

    def test_progress_does_not_reset_models(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp:
            controller = Controller(Mock(), Path(temp) / 'settings.json')
            resets = []
            controller.rowsChanged.connect(lambda: resets.append(True))
            controller.receive('counts', (25, 100))
            self.assertEqual(resets, [])
            self.assertEqual(controller.completed, 25)

    def test_malformed_saved_locations_are_recoverable(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp:
            config = Path(temp) / 'settings.json'
            config.write_text('{"roots": ["Z:/", null]}')
            controller = Controller(Mock(), config)
            self.assertEqual(controller.roots, [])
            self.assertIn('Could not load', controller.status)

    def test_async_search_previews_and_relink_progress(self):
        app = QGuiApplication.instance() or QGuiApplication([])
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp:
            path = str(Path(temp) / 'clip.mov')
            Path(path).touch()
            bridge = Mock()
            def request(command, **kwargs):
                if command == 'inventory':
                    return [dict(key='0', name='Clip', old='X:/missing/clip.mov', target='', status='Searching', thumbnail='', previewLabel='No preview available')]
                if command == 'relink':
                    return True
                return ''
            bridge.request.side_effect = request
            controller = Controller(bridge, Path(temp) / 'settings.json')
            controller._roots = [dict(name='Media', path=temp)]
            def wait_finished():
                loop = QEventLoop()
                controller.changed.connect(lambda: loop.quit() if not controller.busy else None)
                QTimer.singleShot(5000, loop.quit)
                loop.exec()
                for worker in list(controller.workers):
                    worker.wait(1000)
                app.processEvents()
                self.assertFalse(controller.busy)
            with patch('qt_app.file_thumbnail', return_value='data:image/jpeg;base64,test'):
                controller.find()
                wait_finished()
            self.assertTrue(controller.scan_complete)
            self.assertEqual(controller.rows[0]['target'], path)
            self.assertEqual(controller.completed, controller.total)
            self.assertEqual(controller.rows[0]['previewLabel'], 'Found source preview')
            controller.relink()
            wait_finished()
            self.assertEqual(controller.rows[0]['status'], 'Relinked')
            self.assertEqual((controller.completed, controller.total), (1, 1))

    def test_qml_loads_and_renders_with_locations_and_media(self):
        QQuickStyle.setStyle('Basic')
        app = QGuiApplication.instance() or QGuiApplication([])
        load_fonts()
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp:
            controller = Controller(Mock(), Path(temp) / 'settings.json')
            controller._roots = [dict(name='Footage Archive', path='Z:/Footage'), dict(name='Camera Originals', path='Y:/Camera')]
            controller._rows = [dict(key='0', name='Camera A - Take 01', old='X:/Camera/C001.mov', target='Z:/Footage/C001.mov', status='Match', thumbnail='', previewLabel='No preview available')]
            preview = Path('qa-artifacts/live/verified-thumbnail.jpg').resolve()
            if preview.exists():
                controller._rows[0].update(thumbnail=preview.as_uri(), previewLabel='Generated QA footage')
            controller._rows.extend([
                dict(key='1', name='Interview - Camera B', old='X:/Card02/C002.mov', target='', status='Choose duplicate', thumbnail='', previewLabel='Choose a source to preview'),
                dict(key='2', name='Location audio.wav', old='X:/Sound/Location audio.wav', target='', status='Not found', thumbnail='', previewLabel='No preview available')
            ])
            controller._phase = 'Complete'
            controller._status = '3 missing clips · 1 match · 1 duplicate · 1 not found'
            controller._done, controller._total = 3, 3
            engine = QQmlApplicationEngine()
            warnings = []
            engine.warnings.connect(lambda errors: warnings.extend(e.toString() for e in errors))
            engine.rootContext().setContextProperty('backend', controller)
            engine.load(QUrl.fromLocalFile(str(Path('Main.qml').resolve())))
            self.assertTrue(engine.rootObjects(), '\n'.join(warnings))
            for _ in range(12):
                app.processEvents()
            loading = QEventLoop()
            QTimer.singleShot(250, loading.quit)
            loading.exec()
            root = engine.rootObjects()[0]
            image = root.grabWindow()
            self.assertFalse(image.isNull())
            (PROJECT_ROOT / 'qa-artifacts').mkdir(exist_ok=True)
            image.save(str(PROJECT_ROOT / 'qa-artifacts/ui-preview.png'))
            root.setWidth(1000)
            root.setHeight(620)
            for _ in range(8):
                app.processEvents()
            artifacts = Path('qa-artifacts')
            artifacts.mkdir(exist_ok=True)
            root.grabWindow().save(str(artifacts / 'ui-minimum.png'))
            self.assertFalse(warnings, '\n'.join(warnings))
            root.close()
            engine.deleteLater()
            app.processEvents()


if __name__ == '__main__':
    unittest.main()
