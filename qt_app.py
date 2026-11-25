"""Qt Quick frontend; no Resolve or Qt libraries are loaded into each other."""
import base64
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import threading
import argparse
import time
from copy import deepcopy

from PySide6.QtCore import QObject, Property, Signal, Slot, QThread, QUrl, QTimer
from PySide6.QtGui import QGuiApplication, QFontDatabase, QIcon
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from relink_core import filename, location_name, protected_location
from version import VERSION
from search_engine import search, search_index_first, index_disk_usage, format_bytes, FileIndex, canonical, roots_for_search
from auto_index import ChangeMonitor, apply_changes
from app_update import RELEASES_URL, installer_asset, installed_app, download_installer, run_installer, discard_installer


LATEST_RELEASE_API = 'https://api.github.com/repos/technicallyalex/MultiDiskSearch/releases/latest'


def release_version(tag):
    match = re.fullmatch(r'v?(\d{1,9})\.(\d{1,9})\.(\d{1,9})', tag, re.ASCII)
    if not match:
        raise ValueError('Invalid release version')
    return tuple(map(int, match.groups()))


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
            raise RuntimeError('Resolve connection closed. Reopen Workspace > Workflow Integrations > MultiDiskSearch.')
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
    updateChanged = Signal()
    changed = Signal()
    rowsChanged = Signal()
    rootsChanged = Signal()
    candidatesReady = Signal('QVariantList', int)
    autoChange = Signal(str, object)
    watchStateChanged = Signal(str, str)
    appVersion = Property(str, lambda self: VERSION, constant=True)
    connected = Property(bool, lambda self: self.bridge is not None, constant=True)

    def __init__(self, bridge, config=None, monitor=False):
        super().__init__()
        self.bridge = bridge
        self._update_network = None
        self._update_reply = None
        self._update_worker = None
        self._update_cancel = threading.Event()
        self._update_installer = None
        self._update_status = ''
        self._update_url = ''
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
        self._scope = 'project'
        self._method = 'direct'
        self._max_workers = 0
        self._index_folder = str(self.config.parent / 'Index')
        self._timeline_name = ''
        self._location_states = {}
        self._index_labels = {}
        self._index_disk_size = '0 B'
        self._auto_enabled = True
        self._allow_monitor = monitor
        self._monitor = None
        self._monitor_signature = None
        self._auto_pending = {}
        self._auto_retry = {}
        self._auto_active = {}
        self._auto_worker = None
        self._auto_cancel = threading.Event()
        self._watch_states = {}
        self._auto_status = 'Starting' if monitor else 'Not running'
        self.autoChange.connect(self.queue_auto_change)
        self.watchStateChanged.connect(self.receive_watch_state)
        self._auto_timer = QTimer(self)
        self._auto_timer.setInterval(2000)
        self._auto_timer.timeout.connect(self.process_auto_changes)
        try:
            settings = json.loads(self.config.read_text(encoding='utf-8-sig'))
            if not isinstance(settings, dict) or not isinstance(settings.get('roots', []), list):
                raise ValueError('Saved locations must be a list.')
            for path in settings.get('roots', []):
                if not isinstance(path, str) or not path.strip():
                    raise ValueError('Each saved location must be a non-empty path.')
                self._roots.append(dict(name=location_name(path), path=path))
            self._scope = settings.get('scope', 'project') if settings.get('scope') in ('project', 'timeline') else 'project'
            self._method = settings.get('method', 'direct') if settings.get('method') in ('direct', 'index', 'index_first') else 'direct'
            worker_limit = settings.get('worker_limit', 0)
            if type(worker_limit) is int and 0 <= worker_limit <= 8:
                self._max_workers = worker_limit
            self._auto_enabled = settings.get('auto_index', True) is True
            folder = settings.get('index_folder')
            if isinstance(folder, str) and folder.strip():
                self._index_folder = folder
        except FileNotFoundError:
            pass
        except (ValueError, OSError, TypeError) as error:
            self._roots = []
            self._status = 'Could not load locations: ' + str(error)
        try:
            if (Path(self._index_folder) / 'files.sqlite3').is_file():
                self._index_labels = self.index_labels()
        except Exception as error:
            self._status = 'Index unavailable: ' + str(error) + '. Rebuild the index or search drives directly.'
        self.refreshIndexUsage()
        if monitor:
            self._auto_timer.start()
            QTimer.singleShot(0, self.sync_monitor)

    updateChecking = Property(bool, lambda self: self._update_reply is not None or
                              self._update_worker is not None or self._update_installer is not None, notify=updateChanged)
    updateStatus = Property(str, lambda self: self._update_status, notify=updateChanged)
    updateUrl = Property(str, lambda self: self._update_url, notify=updateChanged)

    @Slot()
    def checkForUpdates(self):
        if self.updateChecking:
            return
        if self._update_network is None:
            self._update_network = QNetworkAccessManager(self)
        request = QNetworkRequest(QUrl(LATEST_RELEASE_API))
        request.setTransferTimeout(10000)
        request.setRawHeader(b'Accept', b'application/vnd.github+json')
        request.setRawHeader(b'User-Agent', f'MultiDiskSearch/{VERSION}'.encode('ascii'))
        reply = self._update_network.get(request)
        self._update_reply = reply
        self._update_url = ''
        self._update_status = ''
        reply.finished.connect(self.finishUpdateCheck)
        # Bound the full request, including connections that keep sending small chunks.
        deadline = QTimer(reply)
        deadline.setSingleShot(True)
        deadline.timeout.connect(reply.abort)
        deadline.start(15000)
        self.updateChanged.emit()

    @Slot()
    def finishUpdateCheck(self):
        reply = self._update_reply
        self._update_reply = None
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
                if status == 404:
                    self._update_status = 'No published stable release found.'
                else:
                    self._update_status = 'Could not check GitHub. Try again later.'
            else:
                release = json.loads(bytes(reply.readAll()))
                tag = release['tag_name']
                if release['draft'] or release['prerelease']:
                    raise ValueError('Expected a stable release')
                if release_version(tag) > release_version(VERSION):
                    self._update_status = f'{tag.lstrip("v")} is available.'
                    self._update_url = f'{RELEASES_URL}/tag/{tag}'
                    asset = installer_asset(release) if installed_app() else None
                    if asset:
                        self.startUpdateDownload(asset)
                else:
                    self._update_status = 'No newer release available.'
        except (KeyError, TypeError, ValueError):
            self._update_status = 'Could not read the release information from GitHub.'
        finally:
            reply.deleteLater()
            self.updateChanged.emit()

    def startUpdateDownload(self, asset):
        self._update_status = 'Downloading update…'
        def task(emit):
            path = download_installer(asset, self._update_cancel, lambda *_: None)
            emit('downloaded', path)
        self._update_worker = Worker(task)
        self._update_worker.event.connect(self.receiveUpdate)
        self._update_worker.finished.connect(self.finishUpdateDownload)
        self._update_worker.start()

    @Slot(str, object)
    def receiveUpdate(self, kind, data):
        if kind == 'downloaded':
            self._update_installer = data
        elif kind == 'error':
            self._update_status = f'Update download failed. {data}'
            self.updateChanged.emit()

    @Slot()
    def finishUpdateDownload(self):
        self._update_worker.deleteLater()
        self._update_worker = None
        if self._update_installer is not None:
            self.applyUpdateWhenIdle()
        self.updateChanged.emit()

    @Slot()
    def applyUpdateWhenIdle(self):
        if self._update_cancel.is_set() or self._update_installer is None:
            return
        if self._busy:
            self._update_status = 'Update ready. Waiting for the current operation to finish.'
            self.updateChanged.emit()
            QTimer.singleShot(1000, self.applyUpdateWhenIdle)
            return
        path = self._update_installer
        self._update_status = 'Approve the Windows prompt to install the update.'
        self.updateChanged.emit()
        try:
            if run_installer(path):
                self._update_installer = None
                QGuiApplication.quit()
                return
            self._update_status = 'Update was cancelled or Windows could not start setup.'
        except OSError:
            self._update_status = 'Windows could not start setup.'
        self._update_installer = None
        self.removeDownloadedUpdate(path)
        self.updateChanged.emit()

    @staticmethod
    def removeDownloadedUpdate(path):
        try:
            discard_installer(path)
        except OSError:
            pass

    def shutdownUpdate(self):
        self._update_cancel.set()
        if self._update_worker is not None:
            self._update_worker.wait()
            # Deliver download completion if it arrived while the event loop was exiting.
            QGuiApplication.processEvents()
        if self._update_installer is not None:
            self.removeDownloadedUpdate(self._update_installer)
            self._update_installer = None

    roots = Property('QVariantList', lambda self: [dict(r,
        scanState=self._location_states.get(canonical(r['path']), {}).get('state', 'Ready'),
        scanDetail=self.location_detail(r['path']),
        indexDetail=self._index_labels.get(canonical(r['path']), 'Not indexed'),
        watchState=self._watch_states.get(canonical(r['path']), '')) for r in self._roots], notify=rootsChanged)
    searchScope = Property(str, lambda self: self._scope, notify=changed)
    searchMethod = Property(str, lambda self: self._method, notify=changed)
    indexFolder = Property(str, lambda self: self._index_folder, notify=changed)
    indexDiskSize = Property(str, lambda self: self._index_disk_size, notify=changed)
    autoIndexEnabled = Property(bool, lambda self: self._auto_enabled, notify=changed)
    autoIndexStatus = Property(str, lambda self: self._auto_status, notify=changed)

    @Slot(bool)
    def setAutoIndex(self, enabled):
        self._auto_enabled = enabled
        self.save()

    @Slot(str, str)
    def receive_watch_state(self, root, state):
        self._watch_states[canonical(root)] = state
        self.rootsChanged.emit()

    def sync_monitor(self):
        if not self._allow_monitor:
            return
        signature = (tuple(r['path'] for r in self._roots), self._index_folder, self._auto_enabled)
        if signature == self._monitor_signature:
            return
        self._monitor_signature = signature
        if self._monitor:
            self._monitor.stop()
            self._monitor = None
        self._auto_cancel.set()
        self._auto_pending.clear()
        self._auto_retry.clear()
        self._watch_states.clear()
        self._auto_status = 'Off' if not self._auto_enabled else 'Waiting for locations' if not self._roots else 'Watching for changes'
        if self._auto_enabled and self._roots:
            self._monitor = ChangeMonitor([r['path'] for r in self._roots], self._index_folder,
                self.autoChange.emit, self.watchStateChanged.emit)
            self._monitor.start()
        self.changed.emit()
        self.rootsChanged.emit()

    @Slot(str, object)
    def queue_auto_change(self, root, paths):
        if not self._auto_enabled or canonical(root) not in roots_for_search([r['path'] for r in self._roots]):
            return
        key = canonical(root)
        item = self._auto_pending.setdefault(key, {'root':root, 'full':False, 'paths':set()})
        if paths is None or len(item['paths']) > 2000:
            item['full'] = True
            item['paths'].clear()
        elif not item['full']:
            item['paths'].update(paths)

    @Slot()
    def process_auto_changes(self):
        if self._auto_enabled:
            for key,(due,root) in list(self._auto_retry.items()):
                if time.monotonic() >= due:
                    self.queue_auto_change(root,None)
                    self._auto_retry.pop(key,None)
        if self._busy or self._auto_worker or not self._auto_enabled or not self._auto_pending:
            return
        pending, self._auto_pending = self._auto_pending, {}
        self._auto_active = pending
        folder, workers = self._index_folder, self._max_workers
        self._auto_cancel.clear()
        self._auto_status = 'Updating index in background'
        def task(emit):
            full, errors = [], []
            for item in pending.values():
                if self._auto_cancel.is_set():
                    break
                if item['full'] or not apply_changes(folder,item['root'],item['paths'],self._auto_cancel):
                    full.append(item['root'])
            if full and not self._auto_cancel.is_set():
                _, errors, _ = search(full,set(),self._auto_cancel,workers=workers,index_folder=folder,refresh=True,
                    update=lambda root,data:emit('progress',(root,data)))
            if not self._auto_cancel.is_set():
                catalog=FileIndex(folder)
                try:
                    labels=catalog.describe([item['root'] for item in pending.values()])
                finally:
                    catalog.close()
                emit('labels',(folder,labels))
                emit('status','Some locations unavailable; reconnect them to resume' if errors else 'Watching for changes')
        worker=Worker(task)
        self._auto_worker=worker
        worker.event.connect(self.receive_auto)
        worker.finished.connect(lambda: self.cleanup_auto(worker))
        worker.start()
        self.changed.emit()

    @Slot(str, object)
    def receive_auto(self, kind, data):
        if kind == 'labels' and data[0] == self._index_folder:
            self._index_labels.update(data[1])
            self.rootsChanged.emit()
            self.refreshIndexUsage()
        elif kind == 'status':
            self._auto_status = data if self._auto_enabled else 'Off'
        elif kind == 'progress' and self._auto_enabled:
            self._auto_status = f'Updating {location_name(data[0])}: {data[1]["folders"]:,} folders checked'
        elif kind == 'error':
            self._auto_status = 'Automatic update failed: ' + str(data) + '. Use Refresh or Rebuild index.'
            if self._auto_enabled:
                for key,item in self._auto_active.items():
                    self._auto_retry[key] = (time.monotonic()+30,item['root'])
        self.changed.emit()

    def cleanup_auto(self, worker):
        self._auto_worker=None
        self._auto_active={}
        worker.deleteLater()

    def shutdown_auto(self):
        self._auto_timer.stop()
        self._auto_cancel.set()
        if self._monitor:
            self._monitor.stop()
            self._monitor=None
        if self._auto_worker:
            self._auto_worker.wait()
    maxWorkers = Property(int, lambda self: self._max_workers, notify=changed)
    timelineName = Property(str, lambda self: self._timeline_name, notify=changed)
    locationSummary = Property(str, lambda self: self.location_summary(), notify=rootsChanged)
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

    def location_detail(self, path):
        data = self._location_states.get(canonical(path), {})
        return f'{data.get("folders", 0):,} folders · {data.get("files", 0):,} files checked' if data else ''

    def location_summary(self):
        states = [v['state'] for v in self._location_states.values()]
        return ' · '.join(f'{states.count(state)} {state.lower()}' for state in
            ('Searching', 'Queued', 'Complete', 'Incomplete', 'Offline', 'Stopped', 'Cancelled', 'Index lookup') if state in states)

    @Slot(str, str, int)
    def configureSearch(self, scope, method, workers):
        if self._busy:
            return
        self._scope = 'timeline' if scope == 'timeline' else 'project'
        self._method = method if method in ('direct', 'index', 'index_first') else 'direct'
        self._max_workers = max(0, min(8, workers))
        self._timeline_name = ''
        self.save()
        self.changed.emit()

    @Slot(QUrl)
    def setIndexFolder(self, url):
        if self._busy or not url.toLocalFile():
            return
        destination = url.toLocalFile()
        previous = self._index_folder
        def task(emit):
            emit('phase', ('Moving file index', 0, 0))
            FileIndex.migrate(previous, destination)
            emit('index_folder', destination)
            emit('status', 'Index folder updated. The original index copy was retained.')
        self.start(task)

    def index_labels(self):
        catalog = FileIndex(self._index_folder)
        try:
            return catalog.describe([r['path'] for r in self._roots])
        finally:
            catalog.close()

    @Slot()
    def refreshIndexUsage(self):
        try:
            value = format_bytes(index_disk_usage(self._index_folder))
        except (OSError, ValueError):
            value = 'Unavailable'
        if value != self._index_disk_size:
            self._index_disk_size = value
            self.changed.emit()

    def refresh_locations(self, roots, rebuild=False):
        if self._busy or not roots:
            return
        self.scan_complete = False
        self._location_states = {}
        self._errors = ''
        self._rows = []
        self.matches = {}
        self.rowsChanged.emit()
        folder, workers = self._index_folder, self._max_workers
        def task(emit):
            emit('phase', ('Refreshing file index', 0, 0))
            if rebuild:
                FileIndex.prepare_rebuild(folder)
            _, errors, stopped = search(roots, set(), self.cancel, workers=workers,
                index_folder=folder, refresh=True, update=lambda root, data: emit('location', (root, data)))
            emit('index_labels', self.index_labels())
            emit('index_finished', None)
            if errors:
                emit('search_errors', '\n'.join(errors))
            emit('status', 'Index refresh stopped; previous snapshots retained.' if stopped else
                 'Index refresh incomplete; previous snapshots retained for failed locations.' if errors else
                 'Index refreshed. Use file index for fast lookups, or direct search for complete current coverage.')
        self.start(task)

    @Slot()
    def refreshIndex(self):
        self.refresh_locations([r['path'] for r in self._roots])

    @Slot()
    def rebuildIndex(self):
        self.refresh_locations([r['path'] for r in self._roots], rebuild=True)

    @Slot(int)
    def refreshLocation(self, index):
        if 0 <= index < len(self._roots):
            self.refresh_locations([self._roots[index]['path']])

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
        if self._auto_worker:
            self._auto_cancel.set()
            for item in self._auto_active.values():
                self.queue_auto_change(item['root'],None)
            self._auto_status = 'Paused while a user operation runs'
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
        elif kind == 'location':
            root, value = data
            self._location_states[root] = value
            self.rootsChanged.emit()
        elif kind == 'index_labels':
            self._index_labels = data
            self.rootsChanged.emit()
            self.refreshIndexUsage()
        elif kind == 'index_folder':
            self._index_folder = data
            self.save()
            self.refreshIndexUsage()
        elif kind == 'index_finished':
            self._rows = []
            self.matches = {}
            self.rowsChanged.emit()
        elif kind == 'search_errors':
            self._errors = data
        elif kind == 'timeline':
            self._timeline_name = data
        elif kind == 'thumbnail':
            index, image, label = data
            self._rows[index] = dict(self._rows[index], thumbnail=image, previewLabel=label)
            self.rowsChanged.emit()
        elif kind == 'matched':
            matches, errors, stopped = data[:3]
            verified = data[3] if len(data) > 3 else set()
            self.matches = matches
            self.scan_complete = not stopped
            self._errors = '\n'.join(errors)
            for row in self._rows:
                candidates = sorted(matches.get(filename(row['old']), []))
                row['target'] = candidates[0] if len(candidates) == 1 and not stopped and (not errors or filename(row['old']) in verified) else ''
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
            temporary.write_text(json.dumps({'roots': [r['path'] for r in self._roots],
                'scope': self._scope, 'method': self._method, 'worker_limit': self._max_workers,
                'index_folder': self._index_folder, 'auto_index':self._auto_enabled}, indent=2), encoding='utf-8')
            temporary.replace(self.config)
        except OSError as error:
            self._status = 'Could not save locations: ' + str(error)
        self._rows = []
        self.matches = {}
        self.scan_complete = False
        self.rowsChanged.emit()
        self.rootsChanged.emit()
        self.changed.emit()
        self.sync_monitor()

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
            self.refresh_locations([path])

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
        scope, method, workers, folder = self._scope, self._method, self._max_workers, self._index_folder
        self._location_states = {}
        def task(emit):
            emit('phase', ('Reading project', 0, 0))
            inventory = self.bridge.request('inventory', scope=scope, with_context=True)
            rows = inventory['rows'] if isinstance(inventory, dict) else inventory
            emit('timeline', inventory.get('timeline', '') if isinstance(inventory, dict) else '')
            emit('rows', rows)
            if not rows:
                emit('status', 'No missing source files in the current project.')
                return
            names = {filename(r['old']) for r in rows}
            update = lambda root, data: emit('location', (root, data))
            if method == 'index_first':
                result = search_index_first(roots, names, self.cancel, workers=workers,
                    index_folder=folder, update=update, phase=lambda text: emit('phase', (text, 0, 0)))
            else:
                emit('phase', ('Searching file index' if method == 'index' else 'Searching drives in parallel', 0, 0))
                result = search(roots, names, self.cancel, workers=workers,
                    index_folder=folder if method == 'index' else None, indexed=method == 'index', update=update)
            if method in ('index', 'index_first'):
                try:
                    emit('index_labels', self.index_labels())
                except Exception:
                    pass  # A failed index must not discard successfully recovered live results.
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
            self.bridge.request('validate_scope')
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
    parser = argparse.ArgumentParser()
    parser.add_argument('port', nargs='?', type=int)
    parser.add_argument('--smoke-test', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--report', help=argparse.SUPPRESS)
    args = parser.parse_args()
    QQuickStyle.setStyle('Basic')
    app = QGuiApplication(sys.argv)
    load_fonts()
    app.setApplicationName('MultiDiskSearch')
    app.setApplicationVersion(VERSION)
    app.setWindowIcon(brand_icon())
    bridge = Bridge(args.port) if args.port is not None else None
    settings_override = os.environ.get('MDS_SETTINGS_PATH')
    controller = Controller(bridge, Path(settings_override) if settings_override else None, monitor=not args.smoke_test)
    if bridge is None:
        controller._status = 'Open Workspace > Workflow Integrations > MultiDiskSearch in Resolve Studio.'
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty('backend', controller)
    warnings = []
    engine.warnings.connect(lambda entries: warnings.extend(entry.toString() for entry in entries))
    engine.load(QUrl.fromLocalFile(str(Path(__file__).with_name('Main.qml').resolve())))
    if not engine.rootObjects():
        controller.shutdown_auto()
        return 1
    if args.smoke_test:
        def finish_smoke():
            window = engine.rootObjects()[0]
            image = window.grabWindow()
            report = {'version':VERSION, 'qml_loaded':True, 'window_icon':not app.windowIcon().isNull(), 'rendered':not image.isNull(), 'warnings':warnings}
            if args.report:
                destination = Path(args.report)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(json.dumps(report, indent=2), encoding='utf-8')
                image.save(str(destination.with_suffix('.png')))
            app.exit(0 if not warnings and report['rendered'] and report['window_icon'] else 2)
        QTimer.singleShot(700, finish_smoke)
    code = app.exec()
    controller.shutdownUpdate()
    controller.shutdown_auto()
    controller.cancel.set()
    for worker in list(controller.workers):
        worker.wait()
    if bridge is not None:
        bridge.stream.close()
        bridge.socket.close()
    return code


if __name__ == '__main__':
    sys.exit(main())
