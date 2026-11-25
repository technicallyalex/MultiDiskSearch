"""Recursive change notifications and transactional incremental catalog updates."""
import os
from pathlib import Path
import threading
import time

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from relink_core import EXCLUDED_DIRS, linked_directory, protected_location
from search_engine import FileIndex, canonical, drive_identity, index_write_lock, roots_for_search


def inside(path, parent):
    path, parent = canonical(path), canonical(parent)
    return path == parent or path.startswith(parent.rstrip(os.sep) + os.sep)


def apply_changes(folder, root, paths, cancel):
    """False requests a full reconciliation; failures/cancellation preserve the snapshot."""
    with index_write_lock(folder):
        catalog = FileIndex(folder)
        try:
            key = canonical(root)
            row = catalog.db.execute('SELECT generation,identity,count FROM roots WHERE root=?', (key,)).fetchone()
            if not row or not os.path.isdir(root) or row[1] != drive_identity(root):
                return False
            if linked_directory(root) or protected_location(root):
                return False
            actual = {canonical(p): os.path.abspath(p) for p in paths if inside(p, root) and not inside(p, folder)}
            changes = [actual[p] for p in roots_for_search(actual)]
            records = {}
            for path in changes:
                stack = [path]
                while stack:
                    if cancel.is_set():
                        return False
                    current = stack.pop()
                    if protected_location(current) or inside(current, folder) or linked_directory(current):
                        continue
                    parent = Path(current).parent
                    safe = True
                    while inside(parent, root) and canonical(parent) != key:
                        if linked_directory(parent):
                            safe = False
                            break
                        parent = parent.parent
                    if not safe:
                        continue
                    try:
                        if os.path.isdir(current):
                            with os.scandir(current) as entries:
                                stack.extend(e.path for e in entries if e.name.casefold() not in EXCLUDED_DIRS)
                        elif os.path.isfile(current):
                            stat = os.stat(current, follow_symlinks=False)
                            records[canonical(current)] = (os.path.abspath(current), Path(current).name.casefold(), stat.st_size, stat.st_mtime_ns)
                    except FileNotFoundError:
                        continue
            if cancel.is_set() or row[1] != drive_identity(root):
                return False
            with catalog.db:
                count = row[2]
                for path in changes:
                    prefix = path.rstrip(os.sep) + os.sep
                    count -= catalog.db.execute('DELETE FROM files WHERE root=? AND generation=? AND path=?',
                        (key, row[0], path)).rowcount
                    count -= catalog.db.execute('DELETE FROM files WHERE root=? AND generation=? AND path>=? AND path<?',
                        (key, row[0], prefix, prefix+'\U0010ffff')).rowcount
                catalog.db.executemany('INSERT OR REPLACE INTO files VALUES(?,?,?,?,?,?)',
                    [(key,row[0],*entry) for entry in records.values()])
                catalog.db.execute('UPDATE roots SET count=?,refreshed=?,error=? WHERE root=?',
                    (count + len(records), time.time(), '', key))
            return True
        finally:
            catalog.close()


class ChangeHandler(FileSystemEventHandler):
    def __init__(self, root, callback, excluded):
        self.root, self.callback, self.excluded = root, callback, excluded

    def on_any_event(self, event):
        if event.event_type == 'events_lost':
            self.callback(self.root, None)
            return
        if event.event_type not in ('created','deleted','moved','modified','attrib'):
            return
        if event.is_directory and event.event_type in ('modified','attrib'):
            return
        paths = {p for p in (event.src_path, getattr(event,'dest_path','')) if p
                 and inside(p,self.root) and not inside(p,self.excluded) and not protected_location(p)}
        if paths:
            self.callback(self.root, paths)


class ChangeMonitor:
    def __init__(self, roots, folder, callback, status=lambda root,state:None, interval=10, fallback=300, reconcile=3600):
        actual = {canonical(p):os.path.abspath(p) for p in roots}
        self.roots = [actual[p] for p in roots_for_search(roots)]
        self.folder, self.callback, self.status = folder, callback, status
        self.interval, self.fallback, self.reconcile = interval, fallback, reconcile
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.run,daemon=True,name='MultiDiskSearch-watch')
        self.observers = {}
        self.pending = {}
        self.pending_lock = threading.Lock()
        self.flusher = threading.Thread(target=self.flush,daemon=True,name='MultiDiskSearch-watch-events')

    def start(self):
        self.flusher.start()
        self.thread.start()

    def enqueue(self, root, paths):
        with self.pending_lock:
            if root in self.pending and self.pending[root] is None:
                return
            if paths is None:
                self.pending[root] = None
            else:
                current = self.pending.setdefault(root,set())
                current.update(paths)
                if len(current) > 2000:
                    self.pending[root] = None

    def flush(self):
        while not self.stop_event.wait(0.5):
            with self.pending_lock:
                pending, self.pending = self.pending, {}
            for root,paths in pending.items():
                self.callback(root,paths)

    def stop(self):
        self.stop_event.set()
        # Observer stop interrupts native directory notification reads.
        for observer in list(self.observers.values()):
            observer.stop()
        if self.thread.is_alive():
            self.thread.join(timeout=3)
        if self.flusher.is_alive():
            self.flusher.join(timeout=1)

    def run(self):
        last_full, last_try, states = {}, {}, {}
        def report(root,state):
            if states.get(root) != state:
                states[root] = state
                self.status(root,state)
        try:
            while not self.stop_event.is_set():
                for root in self.roots:
                    if self.stop_event.is_set():
                        break
                    now = time.monotonic()
                    observer = self.observers.get(root)
                    online = os.path.isdir(root) and not linked_directory(root) and not protected_location(root)
                    alive = observer and observer.is_alive() and bool(observer.emitters) and all(e.is_alive() for e in observer.emitters)
                    if observer and (not online or not alive):
                        observer.stop()
                        observer.join(timeout=2)
                        self.observers.pop(root,None)
                        observer = None
                        last_try.pop(root,None)
                    if not online:
                        last_try.pop(root,None)
                        report(root,'Offline')
                        continue
                    if not observer and now-last_try.get(root,-self.fallback) >= self.fallback:
                        last_try[root] = now
                        candidate = Observer()
                        try:
                            candidate.schedule(ChangeHandler(root,self.enqueue,self.folder),root,recursive=True)
                            candidate.start()
                            if self.stop_event.is_set():
                                candidate.stop()
                                candidate.join(timeout=2)
                                break
                            self.observers[root] = candidate
                            observer = candidate
                            self.callback(root,None)
                            last_full[root] = now
                        except OSError:
                            candidate.stop()
                            if candidate.is_alive():
                                candidate.join(timeout=2)
                    if now-last_full.get(root,-self.reconcile) >= (self.reconcile if observer else self.fallback):
                        self.callback(root,None)
                        last_full[root] = now
                    report(root,'Watching' if observer else 'Periodic refresh')
                self.stop_event.wait(self.interval)
        finally:
            for observer in list(self.observers.values()):
                observer.stop()
            for observer in list(self.observers.values()):
                observer.join(timeout=2)
            self.observers.clear()
