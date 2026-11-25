import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from search_engine import search, search_index_first, index_disk_usage, format_bytes, FileIndex, canonical
from resolve_bridge import Session


class SearchFeatures(unittest.TestCase):
    def test_auto_workers_fill_independent_slots_and_cap_network_activity(self):
        with tempfile.TemporaryDirectory() as temp:
            groups = [('server:a',), ('server:a',), ('server:b',), ('server:c',),
                      ('disk:0',), ('disk:0',), ('disk:1',)]
            roots = [Path(temp) / str(i) for i in range(len(groups))]
            identities = {canonical(root): set(keys) for root, keys in zip(roots, groups)}
            for root in roots:
                root.mkdir()
                (root / 'clip.mov').touch()
            active = set()
            peak = 0

            def update(root, state):
                nonlocal peak
                if state['state'] == 'Searching':
                    self.assertFalse(active & identities[root])
                    active.update(identities[root])
                    self.assertLessEqual(sum(key.startswith('server:') for key in active), 2)
                    peak = max(peak, len(active))
                elif state['state'] == 'Complete':
                    active.difference_update(identities[root])

            with patch('search_engine.os.process_cpu_count', return_value=8):
                found, errors, stopped = search([str(root) for root in roots], {'clip.mov'},
                    threading.Event(), group=identities.__getitem__, update=update)
            self.assertEqual(peak, 4)
            self.assertEqual(len(found['clip.mov']), len(roots))
            self.assertFalse(errors or stopped)

    def test_index_first_only_scans_missing_filenames(self):
        with tempfile.TemporaryDirectory() as temp:
            root, folder = Path(temp)/'Media',Path(temp)/'Index'
            root.mkdir()
            (root/'cached.mov').touch()
            search([str(root)],set(),threading.Event(),refresh=True,index_folder=folder)
            (root/'new.mov').touch()
            with patch('search_engine.search',wraps=search) as searches:
                matches, notes, stopped, verified = search_index_first([str(root)],{'cached.mov','new.mov'},
                    threading.Event(),index_folder=folder)
            self.assertEqual(searches.call_count,2)
            self.assertEqual(searches.call_args_list[1].args[1],{'new.mov'})
            self.assertTrue(matches['cached.mov'] and matches['new.mov'])
            self.assertTrue(notes)
            self.assertFalse(stopped)
            self.assertEqual(verified,{'new.mov'})

    def test_index_hits_skip_disk_scan_and_cancellation_prevents_fallback(self):
        cached=({'clip.mov':{'E:/clip.mov'}},['Snapshot requires review'],False)
        with patch('search_engine.search',return_value=cached) as searches:
            result=search_index_first(['E:/'],{'clip.mov'},threading.Event(),index_folder='unused')
            self.assertEqual(searches.call_count,1)
            self.assertEqual(result[3],set())
        with patch('search_engine.search',return_value=({'clip.mov':set()},[],True)) as searches:
            result=search_index_first(['E:/'],{'clip.mov'},threading.Event(),index_folder='unused')
            self.assertEqual(searches.call_count,1)
            self.assertTrue(result[2])

    def test_missing_deleted_or_corrupt_index_falls_back_to_live_search(self):
        with tempfile.TemporaryDirectory() as temp:
            root,folder=Path(temp)/'Media',Path(temp)/'Index'
            root.mkdir()
            old=root/'clip.mov'
            old.touch()
            search([str(root)],set(),threading.Event(),refresh=True,index_folder=folder)
            old.unlink()
            (root/'Moved').mkdir()
            target=root/'Moved/clip.mov'
            target.touch()
            for corrupt in (False,True):
                if corrupt:
                    (folder/'files.sqlite3').write_bytes(b'broken index')
                matches, errors, stopped, verified=search_index_first([str(root)],{'clip.mov'},
                    threading.Event(),index_folder=folder)
                self.assertEqual(matches['clip.mov'],{str(target)})
                self.assertEqual(errors,[])
                self.assertFalse(stopped)
                self.assertEqual(verified,{'clip.mov'})

    def test_incomplete_fallback_does_not_mark_live_matches_verified(self):
        with patch('search_engine.search',side_effect=[({'clip.mov':set()},['No index'],False),
                ({'clip.mov':{'E:/clip.mov'}},['Unavailable drive'],False)]):
            matches,errors,stopped,verified=search_index_first(['E:/'],{'clip.mov'},threading.Event(),index_folder='unused')
        self.assertTrue(matches['clip.mov'])
        self.assertEqual(errors,['Unavailable drive'])
        self.assertFalse(verified)

    def test_disk_usage_includes_only_index_owned_files(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            self.assertEqual(index_disk_usage(folder),0)
            catalog=FileIndex(folder)
            catalog.close()
            initial=index_disk_usage(folder)
            self.assertGreater(initial,0)
            (folder/'unrelated.mov').write_bytes(b'x'*16000)
            self.assertEqual(index_disk_usage(folder),initial)
            (folder/'files.sqlite3-journal').write_bytes(b'x'*8192)
            journal=index_disk_usage(folder)
            self.assertGreaterEqual(journal,initial+8192)
            (folder/'files-corrupt-test.sqlite3').write_bytes(b'x'*8192)
            self.assertGreaterEqual(index_disk_usage(folder),journal+8192)
            self.assertEqual(format_bytes(1024**2),'1.0 MiB')

    def test_parallel_scans_match_sequential_and_overlap_is_pruned(self):
        with tempfile.TemporaryDirectory() as temp:
            roots = []
            for name in ('A', 'B', 'C'):
                root = Path(temp) / name
                (root / 'Footage').mkdir(parents=True)
                (root / 'Footage/clip.mov').touch()
                (root / 'Windows').mkdir()
                (root / 'Windows/hidden.mov').touch()
                roots.append(str(root))
            active, max_active, lock = set(), [0], threading.Lock()
            def update(root, state):
                with lock:
                    if state['state'] == 'Searching':
                        active.add(root)
                    else:
                        active.discard(root)
                    max_active[0] = max(max_active[0], len(active))
            wanted = {'clip.mov', 'hidden.mov'}
            baseline = search(roots, wanted, threading.Event(), workers=1)
            parallel = search(roots + [roots[0] + '/Footage'], wanted, threading.Event(), workers=3,
                group=lambda root: {root}, update=update)
            self.assertEqual(baseline, parallel)
            self.assertEqual(len(parallel[0]['clip.mov']), 3)
            self.assertFalse(parallel[0]['hidden.mov'])
            self.assertGreater(max_active[0], 1)
            self.assertLessEqual(max_active[0], 3)

    def test_shared_storage_is_serialized(self):
        with tempfile.TemporaryDirectory() as temp:
            roots = [str(Path(temp) / n) for n in ('A', 'B')]
            for root in roots:
                Path(root).mkdir()
            active = set()
            def update(root, data):
                if data['state'] == 'Searching':
                    active.add(root)
                    self.assertEqual(len(active), 1)
                else:
                    active.discard(root)
            search(roots, set(), threading.Event(), workers=3, group=lambda root: {'same-disk'}, update=update)

    def test_index_snapshot_lookup_refresh_cancel_and_missing_drive(self):
        with tempfile.TemporaryDirectory() as temp:
            root, folder = Path(temp) / 'Media', Path(temp) / 'Index'
            root.mkdir()
            first = root / 'clip.mov'
            first.touch()
            result = search([str(root)], {'clip.mov'}, threading.Event(), refresh=True, index_folder=folder)
            self.assertFalse(result[1])
            with patch('search_engine.os.scandir', side_effect=AssertionError('Cached lookup traversed directories')):
                cached = search([str(root)], {'clip.mov'}, threading.Event(), indexed=True, index_folder=folder)
            self.assertEqual(cached[0], result[0])
            self.assertTrue(cached[1], 'Snapshots require explicit review for unseen duplicates')
            cancelled = threading.Event()
            cancelled.set()
            search([str(root)], set(), cancelled, refresh=True, index_folder=folder)
            store = FileIndex(folder)
            self.assertEqual(store.db.execute('SELECT count FROM roots').fetchone()[0], 1)
            store.close()
            first.unlink()
            self.assertFalse(search([str(root)], {'clip.mov'}, threading.Event(), indexed=True,index_folder=folder)[0]['clip.mov'])
            second = root / 'new.mov'
            second.touch()
            search([str(root)], set(), threading.Event(), refresh=True, index_folder=folder)
            store = FileIndex(folder)
            self.assertEqual(store.db.execute('SELECT name FROM files').fetchall(), [('new.mov',)])
            store.close()
            root.rename(Path(temp) / 'Disconnected')
            self.assertTrue(search([str(root)], {'new.mov'},threading.Event(),indexed=True,index_folder=folder)[1])

    def test_index_migration_preserves_original_and_rejects_existing_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            old,new = Path(temp)/'Old',Path(temp)/'New'
            catalog = FileIndex(old)
            catalog.close()
            FileIndex.migrate(old,new)
            self.assertTrue((old/'files.sqlite3').exists())
            with sqlite3.connect(new/'files.sqlite3') as db:
                self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            db.close()
            with self.assertRaises(ValueError):
                FileIndex.migrate(old,new)

    def test_writer_failure_does_not_deadlock_workers(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/'Media'
            root.mkdir()
            for i in range(450):
                (root/f'{i}.mov').touch()
            with patch('search_engine.FileIndex', side_effect=sqlite3.DatabaseError('corrupt index')):
                with self.assertRaises(sqlite3.DatabaseError):
                    search([str(root)],set(),threading.Event(),refresh=True,index_folder=Path(temp)/'Index')

    def test_interrupted_refresh_preserves_previous_generation_and_corrupt_rebuild(self):
        with tempfile.TemporaryDirectory() as temp:
            root, folder = Path(temp)/'Media', Path(temp)/'Index'
            root.mkdir()
            (root/'old.mov').touch()
            search([str(root)],set(),threading.Event(),refresh=True,index_folder=folder)
            store=FileIndex(folder)
            original=store.db.execute('SELECT generation FROM roots').fetchone()[0]
            store.close()
            for i in range(60):
                (root/str(i)).mkdir()
            cancel=threading.Event()
            def stop(root,data):
                if data['folders']>=25:
                    cancel.set()
            search([str(root)],set(),cancel,refresh=True,index_folder=folder,update=stop)
            store=FileIndex(folder)
            self.assertEqual(store.db.execute('SELECT generation FROM roots').fetchone()[0],original)
            store.close()
            (folder/'files.sqlite3').write_bytes(b'broken database')
            FileIndex.prepare_rebuild(folder)
            self.assertEqual(len(list(folder.glob('files-corrupt-*.sqlite3'))),1)
            search([str(root)],set(),threading.Event(),refresh=True,index_folder=folder)
            store=FileIndex(folder)
            self.assertEqual(store.db.execute('SELECT count FROM roots').fetchone()[0],1)
            store.close()

    def test_root_link_and_drive_identity_change_require_review(self):
        with tempfile.TemporaryDirectory() as temp:
            root, folder = Path(temp)/'Media', Path(temp)/'Index'
            root.mkdir()
            (root/'clip.mov').touch()
            search([str(root)],set(),threading.Event(),refresh=True,index_folder=folder)
            with patch('search_engine.drive_identity',return_value='different-volume'):
                matches, errors, _ = search([str(root)],{'clip.mov'},threading.Event(),indexed=True,index_folder=folder)
            self.assertFalse(matches['clip.mov'])
            self.assertIn('identity changed',errors[0])
            with patch('search_engine.linked_directory',return_value=True):
                matches, errors, _ = search([str(root)],{'clip.mov'},threading.Event())
            self.assertFalse(matches['clip.mov'])
            self.assertTrue(errors)

    def test_timeline_deduplicates_sources_and_guards_changes(self):
        project = Mock()
        project.GetUniqueId.return_value='project'
        timeline = project.GetCurrentTimeline.return_value
        timeline.GetUniqueId.return_value='timeline-a'
        timeline.GetName.return_value='Edit'
        timeline.GetTrackCount.return_value=1
        source=Mock()
        source.GetUniqueId.return_value='source'
        source.GetClipProperty.side_effect=lambda key=None: 'X:/absent/clip.mov' if key else {'File Path':'X:/absent/clip.mov','Clip Name':'Clip'}
        item=Mock()
        item.GetMediaPoolItem.return_value=source
        timeline.GetItemListInTrack.return_value=[item,item]
        resolve=Mock()
        resolve.GetProjectManager.return_value.GetCurrentProject.return_value=project
        session=Session(resolve)
        rows=session.request({'command':'inventory','scope':'timeline','with_context':True})
        self.assertEqual(len(rows['rows']),1)
        self.assertEqual(rows['timeline'],'Edit')
        self.assertTrue(session.request({'command':'validate_scope'}))
        timeline.GetUniqueId.return_value='timeline-b'
        with self.assertRaisesRegex(RuntimeError,'Timeline'):
            session.request({'command':'validate_scope'})
        project.GetCurrentTimeline.return_value=None
        with self.assertRaisesRegex(RuntimeError,'Open a timeline'):
            session.request({'command':'inventory','scope':'timeline'})
