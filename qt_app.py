"""Qt Quick frontend; no Resolve or Qt libraries are loaded into each other."""
import base64
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
from copy import deepcopy

from PySide6.QtCore import QObject, Property, Signal, Slot, QThread, QUrl, QTimer
from PySide6.QtGui import QGuiApplication, QFontDatabase, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from relink_core import scan, filename, location_name, protected_location
from version import VERSION


def load_fonts():
    # Also works when Windows font discovery is unavailable to offscreen Qt.
    font_dir = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
    for name in ('segoeui.ttf', 'segoeuib.ttf'):
        path = font_dir / name
        if path.exists():
            QFontDatabase.addApplicationFont(str(path))


def brand_icon():
    """Use the traced, scalable approved MDS badge."""
    return QIcon(str(Path(__file__).parent / 'assets/brand/mds-icon.svg'))


class Worker(QThread):
    event = Signal(str, object)
    def __init__(self, task):
        super().__init__()
        self.task = task

    def run(self):
        try:
            self.task(self.event.emit)
        except Exception as error:
            self.event.emit('error', str(error))
        finally:
            self.event.emit('finished', None)


class Bridge:
    def __init__(self, port):
        self.socket = socket.create_connection(('127.0.0.1', port), timeout=10)
        self.socket.settimeout(120)
        self.stream = self.socket.makefile('rwb')
        self.stream.write((json.dumps({'token': os.environ.pop('MDS_TOKEN')}) + '\n').encode())
        self.stream.flush()

    def request(self, command, **kwargs):
        self.stream.write((json.dumps(dict(command=command, **kwargs)) + '\n').encode())
        self.stream.flush()
        response = self.stream.readline()
        if not response:
            raise RuntimeError('Resolve connection closed. Reopen this tool from the Scripts menu.')
        response = json.loads(response)
        if 'error' in response:
            raise RuntimeError(response['error'])
        return response['result']


def file_thumbnail(path, cancel):
    """Decode a small local preview, without importing candidates into Resolve."""
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg or cancel.is_set():
        return ''
    try:
        result = subprocess.run([ffmpeg, '-v', 'error', '-nostdin', '-i', path,
                                 '-frames:v', '1', '-vf', 'scale=320:180:force_original_aspect_ratio=decrease',
                                 '-f', 'image2pipe', '-c:v', 'mjpeg', '-'],
                                capture_output=True, timeout=10,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode == 0 and result.stdout:
            return 'data:image/jpeg;base64,' + base64.b64encode(result.stdout).decode()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return ''


class Controller(QObject):
    changed = Signal()
    rowsChanged = Signal()
    rootsChanged = Signal()
    candidatesReady = Signal('QVariantList', int)
    appVersion = Property(str, lambda self: VERSION, constant=True)

    def __init__(self, bridge, config=None):
        super().__init__()
        self.bridge = bridge
        self.config = config or Path(os.environ.get('APPDATA', str(Path.home()))) / 'MultiDiskSearch/settings.json'
        self._roots, self._rows = [], []
        self._busy = False
        self._status = 'Add your media locations, then find missing media.'
        self._phase = 'Ready'
        self._done = self._total = 0
        self._errors = ''
        self.cancel = threading.Event()
        self.matches = {}
        self.workers = []
        self.scan_complete = False
        try:
            settings = json.loads(self.config.read_text(encoding='utf-8-sig'))
            if not isinstance(settings, dict) or not isinstance(settings.get('roots', []), list):
                raise ValueError('Saved locations must be a list.')
            for path in settings.get('roots', []):
                if not isinstance(path, str) or not path.strip():
                    raise ValueError('Each saved location must be a non-empty path.')
                self._roots.append(dict(name=location_name(path), path=path))
        except FileNotFoundError:
            pass
        except (ValueError, OSError) as error:
            self._roots = []
            self._status = 'Could not load locations: ' + str(error)

    roots = Property('QVariantList', lambda self: self._roots, notify=rootsChanged)
    rows = Property('QVariantList', lambda self: self._rows, notify=rowsChanged)
    displayRows = Property('QVariantList', lambda self: self.filtered_rows(), notify=rowsChanged)
    busy = Property(bool, lambda self: self._busy, notify=changed)
    status = Property(str, lambda self: self._status, notify=changed)
    phase = Property(str, lambda self: self._phase, notify=changed)
    completed = Property(int, lambda self: self._done, notify=changed)
    total = Property(int, lambda self: self._total, notify=changed)
    errors = Property(str, lambda self: self._errors, notify=changed)
    readyCount = Property(int, lambda self: sum(bool(r['target']) for r in self._rows), notify=changed)
    duplicateCount = Property(int, lambda self: sum(r['status'] == 'Choose duplicate' for r in self._rows), notify=changed)
    missingCount = Property(int, lambda self: sum(r['status'] == 'Not found' for r in self._rows), notify=changed)

    def filtered_rows(self):
        query = getattr(self, '_query', '').casefold()
        category = getattr(self, '_category', 'All clips')
        return [dict(row, sourceIndex=index) for index, row in enumerate(self._rows)
                if (not query or query in ' '.join(str(row.get(k, '')) for k in ('name', 'old', 'target', 'status')).casefold())
                and (category == 'All clips' or category == 'Ready to relink' and row['target']
                     or category == 'Needs review' and row['status'] in ('Choose duplicate', 'Review source')
                     or category == 'Not found' and row['status'] == 'Not found'
                     or category == 'Relinked' and row['status'] == 'Relinked')]

    @Slot(str, str)
    def setFilter(self, query, category):
        self._query, self._category = query, category
        self.rowsChanged.emit()

    def start(self, task):
        self._busy = True
        self.cancel.clear()
        worker = Worker(task)
        self.workers.append(worker)
        worker.event.connect(self.receive)
        worker.finished.connect(lambda: self.cleanup(worker))
        self.changed.emit()
        worker.start()

    def cleanup(self, worker):
        self.workers.remove(worker)
        worker.deleteLater()

    @Slot(str, object)
    def receive(self, kind, data):
        if kind == 'rows':
            self._rows = deepcopy(data)
            self.rowsChanged.emit()
        elif kind == 'phase':
            self._phase, self._done, self._total = data
        elif kind == 'counts':
            self._phase = 'Searching folders'
            self._done, self._total = data
        elif kind == 'status':
            self._status = data
        elif kind == 'thumbnail':
            index, image, label = data
            self._rows[index] = dict(self._rows[index], thumbnail=image, previewLabel=label)
            self.rowsChanged.emit()
        elif kind == 'matched':
            matches, errors, stopped = data
            self.matches = matches
            self.scan_complete = not stopped
            self._errors = '\n'.join(errors)
            for row in self._rows:
                candidates = sorted(matches.get(filename(row['old']), []))
                row['target'] = candidates[0] if len(candidates) == 1 and not stopped and not errors else ''
                row['status'] = 'Search stopped' if stopped else 'Match' if row['target'] else 'Review source' if candidates and errors else 'Choose duplicate' if candidates else 'Not found'
            self._status = f'{len(self._rows)} missing clips · {sum(bool(r["target"]) for r in self._rows)} matches · {len(errors)} search errors'
            if errors:
                self._status += '. Incomplete coverage: review sources before relinking.'
            self.rowsChanged.emit()
        elif kind == 'relinked':
            index, status = data
            self._rows[index]['status'] = status
            if status == 'Relinked':
                self._rows[index]['target'] = ''
            self.rowsChanged.emit()
        elif kind == 'error':
            self._status = data
            self._phase = 'Error'
        elif kind == 'finished':
            self._busy = False
            if self.cancel.is_set():
                self._phase = 'Stopped'
            elif self._phase != 'Error':
                self._phase = 'Complete'
        self.changed.emit()

    def save(self):
        try:
            self.config.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.config.with_suffix('.tmp')
            temporary.write_text(json.dumps({'roots': [r['path'] for r in self._roots]}, indent=2), encoding='utf-8')
            temporary.replace(self.config)
        except OSError as error:
            self._status = 'Could not save locations: ' + str(error)
        self._rows = []
        self.matches = {}
        self.scan_complete = False
        self.rowsChanged.emit()
        self.rootsChanged.emit()
        self.changed.emit()

    @Slot(QUrl)
    def addLocation(self, url):
        if self._busy:
            return
        path = url.toLocalFile()
        if protected_location(path):
            self._status = 'Protected system locations are excluded. Choose a media folder.'
            self.changed.emit()
            return
        if path and os.path.normcase(os.path.abspath(path)) not in [os.path.normcase(os.path.abspath(r['path'])) for r in self._roots]:
            self._roots.append(dict(name=location_name(path), path=path))
            self.save()

    @Slot(int)
    def removeLocation(self, index):
        if not self._busy and 0 <= index < len(self._roots):
            self._roots.pop(index)
            self.save()

    @Slot()
    def stop(self):
        self.cancel.set()
        self._status = 'Stopping after the current folder or clip…'
        self.changed.emit()

    @Slot()
    def find(self):
        if self._busy:
            return
        if not self._roots:
            self._status = 'Add at least one media location.'
            self.changed.emit()
            return
        self.scan_complete = False
        self._rows = []
        self.rowsChanged.emit()
        self._errors = ''
        roots = [r['path'] for r in self._roots]
        def task(emit):
            emit('phase', ('Reading project', 0, 0))
            rows = self.bridge.request('inventory')
            emit('rows', rows)
            if not rows:
                emit('status', 'No missing source files in the current project.')
                return
            emit('phase', ('Discovering folders', 0, 0))
            result = scan(roots, {filename(r['old']) for r in rows}, self.cancel,
                          lambda text: emit('status', text),
                          lambda done, total: emit('counts', (done, total)))
            emit('matched', result)
            if self.cancel.is_set():
                return
            emit('phase', ('Loading previews', 0, len(rows)))
            for index, row in enumerate(rows):
                if self.cancel.is_set():
                    break
                candidates = result[0].get(filename(row['old']), set())
                image = file_thumbnail(next(iter(candidates)), self.cancel) if len(candidates) == 1 else ''
                label = 'Found source preview'
                if not image:
                    try:
                        image = self.bridge.request('thumbnail', key=row['key'])
                    except Exception:
                        image = ''
                    label = 'Resolve preview'
                if image:
                    emit('thumbnail', (index, image, label))
                emit('phase', ('Loading previews', index + 1, len(rows)))
        self.start(task)

    @Slot(int)
    def showCandidates(self, index):
        if self._busy or not self.scan_complete or not 0 <= index < len(self._rows):
            return
        paths = sorted(self.matches.get(filename(self._rows[index]['old']), []))
        self.candidatesReady.emit(paths, index)

    @Slot(int, str)
    def chooseCandidate(self, index, path):
        if self._busy or not self.scan_complete or not 0 <= index < len(self._rows):
            return
        row = self._rows[index]
        if path in self.matches.get(filename(row['old']), []):
            row.update(target=path, status='Chosen')
            self.rowsChanged.emit()
            self.changed.emit()
            def task(emit):
                emit('phase', ('Loading chosen preview', 0, 1))
                image = file_thumbnail(path, self.cancel)
                emit('thumbnail', (index, image, 'Chosen source preview' if image else 'No preview available'))
                emit('phase', ('Loading chosen preview', 1, 1))
            self.start(task)

    @Slot()
    def relink(self):
        if self._busy or not self.scan_complete:
            return
        selected = [(i, dict(r)) for i, r in enumerate(self._rows) if r['target']]
        def task(emit):
            success = failed = 0
            emit('phase', ('Relinking clips', 0, len(selected)))
            for done, (index, row) in enumerate(selected, 1):
                if self.cancel.is_set():
                    break
                try:
                    self.bridge.request('relink', key=row['key'], target=row['target'])
                    emit('relinked', (index, 'Relinked'))
                    success += 1
                except Exception as error:
                    emit('relinked', (index, str(error)))
                    failed += 1
                emit('phase', ('Relinking clips', done, len(selected)))
            emit('status', f'{success} relinked · {failed} failed. Save the project in Resolve.')
        self.start(task)


def main():
    QQuickStyle.setStyle('Basic')
    app = QGuiApplication(sys.argv)
    load_fonts()
    app.setApplicationName('Multi Disk Search')
    app.setApplicationVersion(VERSION)
    app.setWindowIcon(brand_icon())
    bridge = Bridge(int(sys.argv[1]))
    settings_override = os.environ.get('MDS_SETTINGS_PATH')
    controller = Controller(bridge, Path(settings_override) if settings_override else None)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty('backend', controller)
    engine.load(QUrl.fromLocalFile(str(Path(__file__).with_name('Main.qml').resolve())))
    if not engine.rootObjects():
        return 1
    code = app.exec()
    controller.cancel.set()
    for worker in list(controller.workers):
        worker.wait()
    bridge.stream.close()
    bridge.socket.close()
    return code


if __name__ == '__main__':
    sys.exit(main())
