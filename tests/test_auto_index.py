import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from PySide6.QtGui import QGuiApplication
from watchdog.events import DirCreatedEvent, DirModifiedEvent, EventsLostEvent, FileMovedEvent
from auto_index import ChangeHandler, apply_changes
from search_engine import search, FileIndex, canonical
from qt_app import Controller


class AutomaticIndexTests(unittest.TestCase):
    def test_incremental_move_delete_and_cancellation_preserve_counts(self):
        with tempfile.TemporaryDirectory() as temp:
            root,folder=Path(temp)/'Media',Path(temp)/'Index'
            root.mkdir()
            old=root/'Old'
            old.mkdir()
            (old/'one.mov').touch()
            search([str(root)],set(),threading.Event(),index_folder=folder,refresh=True)
            new=root/'Moved'
            old.rename(new)
            self.assertTrue(apply_changes(folder,str(root),{str(old),str(new)},threading.Event()))
            catalog=FileIndex(folder)
            self.assertEqual(catalog.db.execute('SELECT path FROM files').fetchall(),[(str(new/'one.mov'),)])
            self.assertEqual(catalog.db.execute('SELECT count FROM roots').fetchone()[0],1)
            catalog.close()
            stopped=threading.Event();stopped.set()
            (new/'one.mov').unlink()
            self.assertFalse(apply_changes(folder,str(root),{str(new)},stopped))
            catalog=FileIndex(folder)
            self.assertEqual(catalog.db.execute('SELECT count FROM roots').fetchone()[0],1)
            catalog.close()
            self.assertTrue(apply_changes(folder,str(root),{str(new)},threading.Event()))
            catalog=FileIndex(folder)
            self.assertEqual(catalog.db.execute('SELECT count FROM roots').fetchone()[0],0)
            catalog.close()

    def test_notifications_filter_index_system_folders_and_detect_loss(self):
        with tempfile.TemporaryDirectory() as temp:
            root=str(Path(temp)/'Media')
            folder=str(Path(root)/'Index')
            callback=Mock()
            handler=ChangeHandler(root,callback,folder)
            handler.on_any_event(DirModifiedEvent(root))
            handler.on_any_event(DirCreatedEvent(folder))
            handler.on_any_event(DirCreatedEvent(str(Path(root)/'Windows')))
            callback.assert_not_called()
            handler.on_any_event(FileMovedEvent(str(Path(root)/'old.mov'),str(Path(root)/'new.mov')))
            self.assertEqual(len(callback.call_args.args[1]),2)
            handler.on_any_event(EventsLostEvent(root,is_directory=True))
            self.assertIsNone(callback.call_args.args[1])

    def test_live_recursive_notifications_update_the_catalog(self):
        app=QGuiApplication.instance() or QGuiApplication([])
        with tempfile.TemporaryDirectory() as temp:
            root,folder=Path(temp)/'Media',Path(temp)/'Index'
            root.mkdir()
            search([str(root)],set(),threading.Event(),index_folder=folder,refresh=True)
            config=Path(temp)/'settings.json'
            config.write_text(json.dumps({'roots':[str(root)],'index_folder':str(folder)}),encoding='utf-8')
            controller=Controller(Mock(),config,monitor=True)
            controller._auto_timer.setInterval(50)
            def paths():
                db=sqlite3.connect(folder/'files.sqlite3',timeout=.2)
                try:
                    return {r[0] for r in db.execute('SELECT path FROM files')}
                finally:
                    db.close()
            def until(condition):
                deadline=time.monotonic()+12
                while time.monotonic()<deadline:
                    app.processEvents()
                    if condition():
                        return
                    time.sleep(.025)
                self.fail('Automatic update timed out: '+controller.autoIndexStatus)
            try:
                until(lambda: 'Watching' in controller._watch_states.values() and controller._auto_worker is None and not controller._auto_pending)
                with patch('qt_app.search',wraps=search) as scans:
                    nested=root/'New/Subfolder'
                    nested.mkdir(parents=True)
                    clip=nested/'clip.mov';clip.write_bytes(b'video')
                    until(lambda:str(clip) in paths())
                    moved=root/'Renamed'
                    (root/'New').rename(moved)
                    new_clip=moved/'Subfolder/clip.mov'
                    until(lambda: paths()=={str(new_clip)})
                    renamed=new_clip.with_name('take.mov')
                    new_clip.rename(renamed)
                    until(lambda:paths()=={str(renamed)})
                    self.assertTrue(moved.resolve().is_relative_to(Path(temp).resolve()))
                    shutil.rmtree(moved)
                    until(lambda:not paths())
                    self.assertEqual(scans.call_count,0,'Normal notifications should not rescan the entire root')
                controller.setAutoIndex(False)
                self.assertEqual(controller.autoIndexStatus,'Off')
                self.assertFalse(json.loads(config.read_text(encoding='utf-8'))['auto_index'])
            finally:
                controller.shutdown_auto()
                app.processEvents()
