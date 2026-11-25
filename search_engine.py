"""Bounded storage-aware scanning and a local, metadata-only SQLite catalog."""
import ctypes
import json
import ntpath
import os
from pathlib import Path
import queue
import sqlite3
import threading
import time
import uuid
import hashlib
import functools
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, closing

from relink_core import EXCLUDED_DIRS, filename, linked_directory, protected_location


_catalog_locks = {}
_catalog_locks_guard = threading.Lock()


@contextmanager
def index_write_lock(folder):
    key = canonical(folder)
    with _catalog_locks_guard:
        lock = _catalog_locks.setdefault(key, threading.RLock())
    with lock:
        handle = None
        if os.name == 'nt':
            from ctypes import wintypes
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
            kernel.CreateMutexW.restype = wintypes.HANDLE
            kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            kernel.ReleaseMutex.argtypes = [wintypes.HANDLE]
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            handle = kernel.CreateMutexW(None, False, 'Local\\MultiDiskSearchIndex-' + hashlib.sha256(key.encode()).hexdigest())
            if not handle:
                raise ctypes.WinError(ctypes.get_last_error())
            result = kernel.WaitForSingleObject(handle, 30000)
            if result not in (0, 0x80):
                kernel.CloseHandle(handle)
                raise TimeoutError('The file index is being updated by another instance. Try again shortly.')
        try:
            yield
        finally:
            if handle:
                kernel.ReleaseMutex(handle)
                kernel.CloseHandle(handle)


def catalog_write(function):
    @functools.wraps(function)
    def wrapped(folder, *args, **kwargs):
        with index_write_lock(folder):
            return function(folder, *args, **kwargs)
    return wrapped


def index_disk_usage(folder):
    """Allocated bytes for our catalog, SQLite working files and recovery backups."""
    folder = Path(folder)
    paths = [folder / ('files.sqlite3' + suffix) for suffix in ('', '-journal', '-wal', '-shm')]
    if folder.exists():
        paths.extend(folder.glob('files-corrupt-*.sqlite3*'))
    total = 0
    for path in set(paths):
        try:
            stat = path.stat()
        except FileNotFoundError:
            continue
        if os.name == 'nt':
            from ctypes import wintypes
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            class StandardInfo(ctypes.Structure):
                _fields_ = [('allocation', ctypes.c_longlong), ('length', ctypes.c_longlong),
                            ('links', wintypes.DWORD), ('pending', ctypes.c_ubyte), ('directory', ctypes.c_ubyte)]
            kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                          ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
            kernel.CreateFileW.restype = wintypes.HANDLE
            kernel.GetFileInformationByHandleEx.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            handle = kernel.CreateFileW(str(path), 0x80, 7, None, 3, 0, None)
            if handle in (None, ctypes.c_void_p(-1).value):
                if not path.exists():
                    continue
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                info = StandardInfo()
                if not kernel.GetFileInformationByHandleEx(handle, 1, ctypes.byref(info), ctypes.sizeof(info)):
                    raise ctypes.WinError(ctypes.get_last_error())
                total += info.allocation
            finally:
                kernel.CloseHandle(handle)
        else:
            total += getattr(stat, 'st_blocks', (stat.st_size + 511) // 512) * 512
    return total


def format_bytes(value):
    for unit in ('B', 'KiB', 'MiB', 'GiB', 'TiB'):
        if value < 1024 or unit == 'TiB':
            return f'{value:,.0f} {unit}' if unit == 'B' else f'{value:,.1f} {unit}'
        value /= 1024


def search_index_first(roots, names, cancel, *, index_folder, workers=0,
                       update=lambda root, data: None, phase=lambda text: None):
    """Fall back per filename, retaining conservative review for cached candidates."""
    phase('Searching file index')
    try:
        cached, notes, stopped = search(roots, names, cancel, workers=workers,
            index_folder=index_folder, indexed=True, update=update)
    except (OSError, ValueError, sqlite3.Error) as error:
        cached, notes, stopped = {name: set() for name in names}, [str(error)], cancel.is_set()
    if stopped or cancel.is_set():
        return cached, notes, True, set()
    unresolved = {name for name in names if not cached.get(name)}
    if not unresolved:
        return cached, notes, False, set()
    phase(f'Searching disks for {len(unresolved)} unmatched filenames')
    found, errors, stopped = search(roots, unresolved, cancel, workers=workers, update=update)
    cached.update(found)
    # Index failures are recovered when every requested name receives a complete live scan.
    retained_notes = notes if unresolved != names else []
    return cached, retained_notes + errors, stopped, unresolved if not errors and not stopped else set()


def canonical(path):
    return os.path.normcase(os.path.abspath(path))


def roots_for_search(roots):
    selected = []
    for path in sorted({canonical(p) for p in roots}, key=len):
        if not any(path == parent or path.startswith(parent.rstrip(os.sep) + os.sep) for parent in selected):
            selected.append(path)
    return selected


def storage_keys(path):
    """Group UNC shares by server and Windows volumes by physical disk extents."""
    if path.startswith(('\\\\', '//')):
        return {'server:' + path.replace('/', '\\').strip('\\').split('\\')[0].casefold()}
    if os.name == 'nt':
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        drive, _ = ntpath.splitdrive(path)
        if drive and kernel.GetDriveTypeW(drive + '\\') == 4:  # DRIVE_REMOTE
            remote = ctypes.create_unicode_buffer(32768)
            length = wintypes.DWORD(len(remote))
            connection = ctypes.WinDLL('mpr').WNetGetConnectionW
            connection.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
            connection.restype = wintypes.DWORD
            if connection(drive, remote, ctypes.byref(length)) == 0 and remote.value.startswith('\\\\'):
                return storage_keys(remote.value)
            return {'server:unknown'}
        volume = ctypes.create_unicode_buffer(1024)
        if kernel.GetVolumePathNameW(str(path), volume, len(volume)):
            kernel.CreateFileW.restype = wintypes.HANDLE
            kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                          ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
            handle = kernel.CreateFileW('\\\\.\\' + volume.value.rstrip('\\'), 0, 3, None, 3, 0, None)
            if handle not in (None, ctypes.c_void_p(-1).value):
                buffer, returned = ctypes.create_string_buffer(4096), wintypes.DWORD()
                kernel.DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p,
                    wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
                kernel.CloseHandle.argtypes = [wintypes.HANDLE]
                try:
                    if kernel.DeviceIoControl(handle, 0x560000, None, 0, buffer, len(buffer), ctypes.byref(returned), None):
                        count = int.from_bytes(buffer.raw[:4], 'little')
                        if 0 < count <= 100 and returned.value >= 8 + count * 24:
                            return {'disk:' + str(int.from_bytes(buffer.raw[8+i*24:12+i*24], 'little')) for i in range(count)}
                finally:
                    kernel.CloseHandle(handle)
    # Unknown storage shares one conservative queue rather than assuming drive letters are disks.
    return {'unknown-local'}


def drive_identity(path):
    if os.name == 'nt' and not path.startswith(('\\\\', '//')):
        kernel = ctypes.windll.kernel32
        volume = ctypes.create_unicode_buffer(1024)
        serial = ctypes.c_ulong()
        if kernel.GetVolumePathNameW(path, volume, len(volume)) and kernel.GetVolumeInformationW(
                volume.value, None, 0, ctypes.byref(serial), None, None, None, 0):
            return 'volume:' + str(serial.value)
    return 'path:' + ntpath.splitdrive(path)[0].casefold()


class FileIndex:
    def __init__(self, folder):
        self.folder = Path(folder)
        if str(self.folder).startswith(('\\\\', '//')):
            raise ValueError('Choose a local folder for the file index, not a network share.')
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path = self.folder / 'files.sqlite3'
        self.db = sqlite3.connect(self.path, timeout=10)
        self.db.execute('PRAGMA busy_timeout=10000')
        try:
            self.db.executescript('''
            CREATE TABLE IF NOT EXISTS roots(root TEXT PRIMARY KEY, generation TEXT, refreshed REAL,
                identity TEXT, count INTEGER, error TEXT);
            CREATE TABLE IF NOT EXISTS files(root TEXT, generation TEXT, path TEXT, name TEXT,
                size INTEGER, mtime INTEGER, PRIMARY KEY(root,generation,path));
            CREATE INDEX IF NOT EXISTS file_names ON files(root,generation,name);
            ''')
            self.db.commit()
        except Exception:
            self.db.close()
            raise

    @staticmethod
    @catalog_write
    def prepare_rebuild(folder):
        if str(folder).startswith(('\\\\', '//')):
            raise ValueError('Choose a local index folder.')
        path = Path(folder) / 'files.sqlite3'
        if not path.exists():
            return
        try:
            with closing(sqlite3.connect(path)) as db:
                if db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok':
                    return
        except sqlite3.DatabaseError:
            pass
        backup = path.with_name('files-corrupt-' + uuid.uuid4().hex + '.sqlite3')
        path.replace(backup)
        for suffix in ('-journal', '-wal', '-shm'):
            sidecar = Path(str(path) + suffix)
            if sidecar.exists():
                sidecar.replace(Path(str(backup) + suffix))

    def close(self):
        self.db.close()

    def describe(self, roots):
        result = {}
        for root in roots:
            row = self.db.execute('SELECT refreshed,count,error FROM roots WHERE root=?', (canonical(root),)).fetchone()
            result[canonical(root)] = ('Not indexed' if not row else
                f'{row[1]:,} files · refreshed {time.strftime("%b %d %H:%M", time.localtime(row[0]))}' +
                (' · refresh incomplete' if row[2] else ''))
        return result

    def lookup(self, roots, names, cancel):
        matches, errors = {n: set() for n in names}, []
        for root in roots_for_search(roots):
            if cancel.is_set():
                return matches, errors, True
            row = self.db.execute('SELECT generation,identity FROM roots WHERE root=?', (root,)).fetchone()
            if not row:
                errors.append('Not indexed: ' + root + '. Refresh index or search drives directly.')
                continue
            if not os.path.isdir(root) or linked_directory(root) or protected_location(root):
                errors.append('Unavailable or excluded: ' + root)
                continue
            if row[1] != drive_identity(root):
                errors.append('Drive identity changed: ' + root + '. Refresh this location.')
                continue
            # A cached snapshot cannot rule out new duplicates, regardless of its age.
            errors.append('Cached snapshot: ' + root + '. Review sources or run a fresh direct search.')
            ordered = sorted(names)
            for offset in range(0, len(ordered), 400):
                chunk = ordered[offset:offset+400]
                sql = 'SELECT name,path FROM files WHERE root=? AND generation=? AND name IN (' + ','.join('?' for _ in chunk) + ')'
                for name, path in self.db.execute(sql, (root, row[0], *chunk)):
                    if cancel.is_set():
                        return matches, errors, True
                    if not protected_location(path) and not linked_directory(path) and os.path.isfile(path):
                        # Check parent links too: a directory could have changed after indexing.
                        parent = Path(path).parent
                        while canonical(parent) != root and parent != parent.parent and not linked_directory(parent):
                            parent = parent.parent
                        if not linked_directory(parent):
                            matches[name].add(path)
        return matches, errors, False

    @staticmethod
    @catalog_write
    def migrate(old_folder, new_folder):
        old = Path(old_folder) / 'files.sqlite3'
        new = Path(new_folder) / 'files.sqlite3'
        if canonical(old) == canonical(new):
            return
        if str(new).startswith(('\\\\', '//')):
            raise ValueError('Choose a local index folder.')
        new.parent.mkdir(parents=True, exist_ok=True)
        if new.exists():
            raise ValueError('That folder already contains an index. Choose an empty folder.')
        temporary = new.with_suffix('.moving')
        if temporary.exists():
            raise ValueError('An unfinished index copy exists in that folder. Choose another folder.')
        try:
            with closing(sqlite3.connect(temporary)) as destination:
                if old.exists():
                    with closing(sqlite3.connect(old)) as source:
                        source.backup(destination)
                if destination.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('Index copy verification failed.')
            temporary.replace(new)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise


def search(roots, names, cancel, **kwargs):
    if kwargs.get('refresh') and kwargs.get('index_folder'):
        with index_write_lock(kwargs['index_folder']):
            return _search(roots, names, cancel, **kwargs)
    return _search(roots, names, cancel, **kwargs)


def _search(roots, names, cancel, *, workers=0, update=lambda root, data: None,
           index_folder=None, indexed=False, refresh=False, group=storage_keys):
    actual_roots = {canonical(root): os.path.abspath(root) for root in roots}
    roots = roots_for_search(roots)
    matches, errors = {n: set() for n in names}, []
    catalog = FileIndex(index_folder) if index_folder else None
    try:
        if indexed and not refresh:
            result = catalog.lookup(roots, names, cancel)
            for root in roots:
                update(root, dict(state='Index lookup' if os.path.isdir(root) else 'Offline', folders=0, files=0))
            return result
        events = queue.Queue(maxsize=32)
        abort = threading.Event()
        pending = [(root, group(root)) for root in roots]
        # Enumeration waits on storage, but a bounded pool also limits CPU and write pressure.
        auto = workers == 0
        ceiling = max(2, os.process_cpu_count() or 2) if auto else workers
        capacity = max(1, min(8, ceiling, len(pending)))
        running, occupied = {}, set()
        for root in roots:
            update(root, dict(state='Queued', folders=0, files=0))

        def walk(root):
            folders = files = 0
            issues, batch = [], []
            identity = drive_identity(root)
            def send(kind, data):
                while not abort.is_set():
                    try:
                        events.put((root, kind, data), timeout=0.2)
                        return
                    except queue.Full:
                        continue
            try:
                if protected_location(root) or linked_directory(root):
                    raise OSError('Protected location or directory link is excluded: ' + root)
                if not os.path.isdir(root):
                    raise OSError('Unavailable: ' + root)
                stack = [actual_roots[root]]
                while stack and not cancel.is_set() and not abort.is_set():
                    directory = stack.pop()
                    if linked_directory(directory):
                        issues.append('Directory changed to a link: ' + directory)
                        continue
                    try:
                        with os.scandir(directory) as entries:
                            for entry in entries:
                                if cancel.is_set() or abort.is_set():
                                    break
                                if entry.is_symlink() or linked_directory(entry.path):
                                    continue
                                if index_folder and canonical(entry.path) == canonical(index_folder):
                                    continue
                                if entry.is_dir(follow_symlinks=False):
                                    if entry.name.casefold() not in EXCLUDED_DIRS:
                                        stack.append(entry.path)
                                elif entry.is_file(follow_symlinks=False):
                                    name = entry.name.casefold()
                                    files += 1
                                    if refresh or name in matches:
                                        stat = entry.stat(follow_symlinks=False) if refresh else None
                                        batch.append((os.path.abspath(entry.path), name, stat.st_size if stat else 0, stat.st_mtime_ns if stat else 0))
                                    if len(batch) >= 200:
                                        send('batch', batch)
                                        batch = []
                        folders += 1
                        if folders % 25 == 0:
                            send('progress', dict(state='Searching', folders=folders, files=files))
                    except OSError as error:
                        issues.append(str(error))
                if batch:
                    send('batch', batch)
                if identity != drive_identity(root):
                    issues.append('Drive identity changed during search: ' + root)
            except Exception as error:
                issues.append(str(error))
            finally:
                send('done', (dict(state='Stopped' if cancel.is_set() else 'Incomplete' if issues else 'Complete',
                                   folders=folders, files=files), issues, identity))

        @contextmanager
        def worker_pool():
            pool = ThreadPoolExecutor(max_workers=capacity)
            try:
                yield pool
            finally:
                abort.set()
                pool.shutdown(wait=True)

        with worker_pool() as pool:
            while pending or running:
                if cancel.is_set():
                    for root, _ in pending:
                        update(root, dict(state='Cancelled', folders=0, files=0))
                    pending.clear()
                for item in list(pending):
                    root, keys = item
                    if len(running) >= capacity or occupied & keys:
                        continue
                    if auto and any(key.startswith('server:') for key in keys):
                        active_servers = {key for key in occupied if key.startswith('server:')}
                        if len(active_servers) >= 2 or 'server:unknown' in active_servers or (
                                'server:unknown' in keys and active_servers):
                            continue
                    pending.remove(item)
                    occupied.update(keys)
                    generation = uuid.uuid4().hex
                    running[root] = (keys, generation, pool.submit(walk, root))
                    update(root, dict(state='Searching', folders=0, files=0))
                if not running:
                    break
                root, kind, data = events.get()
                keys, generation, future = running[root]
                if kind == 'batch':
                    for path, name, _, _ in data:
                        if name in matches:
                            matches[name].add(path)
                    if catalog and refresh:
                        catalog.db.executemany('INSERT OR REPLACE INTO files VALUES(?,?,?,?,?,?)',
                            [(root, generation, path, name, size, mtime) for path, name, size, mtime in data])
                        catalog.db.commit()
                elif kind == 'progress':
                    update(root, data)
                elif kind == 'done':
                    status, issues, identity = data
                    future.result()
                    errors.extend(issues)
                    if catalog and refresh:
                        if not issues and not cancel.is_set():
                            with catalog.db:
                                catalog.db.execute('INSERT OR REPLACE INTO roots VALUES(?,?,?,?,?,?)',
                                    (root, generation, time.time(), identity, status['files'], ''))
                                catalog.db.execute('DELETE FROM files WHERE root=? AND generation<>?', (root, generation))
                        else:
                            with catalog.db:
                                catalog.db.execute('DELETE FROM files WHERE root=? AND generation=?', (root, generation))
                                catalog.db.execute('UPDATE roots SET error=? WHERE root=?', ('Incomplete refresh', root))
                    update(root, status)
                    occupied.difference_update(keys)
                    del running[root]
        return matches, errors, cancel.is_set()
    finally:
        if catalog:
            catalog.close()
