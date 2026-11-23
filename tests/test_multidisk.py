import tempfile
import threading
import unittest
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
from unittest.mock import Mock, patch

from relink_core import scan, filename, collect, protected_location, location_name
from resolve_bridge import Session, valid_auth, frontend_command


class SearchTests(unittest.TestCase):
    def test_packaged_runtime_is_used_without_python_dependency(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            executable = Path(temp) / 'MultiDiskSearch.exe'
            executable.touch()
            self.assertEqual(frontend_command(temp, 12345), [str(executable), '12345'])

    def test_malformed_bridge_auth_does_not_crash_host(self):
        for payload in (b'', b'broken', b'[]', b'{"token":12}', b'{"token":"wrong"}'):
            self.assertFalse(valid_auth(payload, 'expected'))
        self.assertTrue(valid_auth(b'{"token":"expected"}', 'expected'))

    def test_root_junction_is_not_traversed(self):
        with patch('relink_core.linked_directory', return_value=True), patch('relink_core.os.walk') as walk:
            found, _, _ = scan(['Z:/MediaLink'], {'clip.mov'}, threading.Event())
            walk.assert_not_called()
            self.assertFalse(found['clip.mov'])

    def test_cancel_reports_actual_completed_count(self):
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp:
            (Path(temp) / 'child').mkdir()
            cancel = threading.Event()
            recorded = []
            def counts(done, total):
                recorded.append((done, total))
                if done == 0:
                    cancel.set()
            _, _, stopped = scan([temp], {'clip.mov'}, cancel, counts=counts)
            self.assertTrue(stopped)
            self.assertEqual(recorded[-1], (0, 2))

    def test_system_folders_are_pruned(self):
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp:
            base = Path(temp)
            for name in ('System Volume Information', '$RECYCLE.BIN', 'Windows', 'Recovery', 'EFI', 'Footage'):
                folder = base / name
                folder.mkdir()
                (folder / 'clip.mov').touch()
            found, errors, stopped = scan([temp], {'clip.mov'}, threading.Event())
            self.assertEqual(found['clip.mov'], {str(base / 'Footage/clip.mov')})
            self.assertEqual(errors, [])
            self.assertFalse(stopped)
            found, _, _ = scan([str(base / 'System Volume Information')], {'clip.mov'}, threading.Event())
            self.assertFalse(found['clip.mov'])

    def test_location_names_and_protected_paths(self):
        self.assertEqual(location_name('Z:/Media/Camera A/'), 'Camera A')
        self.assertTrue(protected_location('Z:/SYSTEM VOLUME INFORMATION/private'))
        self.assertFalse(protected_location('Z:/My Windows footage'))

    def test_multiple_disks_duplicates_and_overlap(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            for directory in ('disk1/card', 'disk2/card'):
                folder = base / directory
                folder.mkdir(parents=True)
                (folder / 'C001.MOV').touch()
            (base / 'disk2/unique.wav').touch()
            found, errors, stopped = scan([str(base / 'disk1'), str(base / 'disk2'), str(base / 'disk1/card')], {'c001.mov', 'unique.wav', 'absent.mp4'}, threading.Event())
            self.assertEqual(len(found['c001.mov']), 2)
            self.assertEqual(len(found['unique.wav']), 1)
            self.assertEqual(found['absent.mp4'], set())
            self.assertEqual(errors, [])
            self.assertFalse(stopped)

    def test_unavailable_and_cancel(self):
        with tempfile.TemporaryDirectory() as temp:
            cancel = threading.Event()
            cancel.set()
            _, errors, stopped = scan([temp + '/absent', temp], {'a.mov'}, cancel)
            self.assertTrue(errors)
            self.assertTrue(stopped)

    def test_windows_filename_and_bins(self):
        self.assertEqual(filename('Z:\\old\\C001.MOV'), 'c001.mov')
        child = Mock()
        child.GetClipList.return_value = ['nested']
        child.GetSubFolderList.return_value = []
        root = Mock()
        root.GetClipList.return_value = ['top']
        root.GetSubFolderList.return_value = [child]
        self.assertEqual(list(collect(root)), ['top', 'nested'])

    def test_native_relink_and_verification(self):
        with tempfile.TemporaryDirectory() as temp:
            target = str(Path(temp) / 'clip.mov')
            Path(target).touch()
            app = Session(Mock())
            app.project = Mock()
            app.project.GetUniqueId.return_value = 'project'
            app.resolve = Mock()
            app.resolve.GetProjectManager.return_value.GetCurrentProject.return_value = app.project
            clip = Mock()
            clip.GetClipProperty.side_effect = ['X:/missing/clip.mov', target]
            app.clips = {'1': (clip, 'X:/missing/clip.mov')}
            self.assertTrue(app.request({'command': 'relink', 'key': '1', 'target': target}))
            app.project.GetMediaPool.return_value.RelinkClips.assert_called_once_with([clip], temp)

    def test_progress_has_real_folder_total(self):
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp:
            (Path(temp) / 'Footage').mkdir()
            (Path(temp) / 'Footage/clip.mov').touch()
            counts = []
            scan([temp], {'clip.mov'}, threading.Event(), counts=lambda done, total: counts.append((done, total)))
            self.assertEqual(counts, [(0, 2), (2, 2)])

    def test_changed_project_is_rejected(self):
        app = Session(Mock())
        app.project = Mock()
        app.project.GetUniqueId.return_value = 'old'
        app.resolve.GetProjectManager.return_value.GetCurrentProject.return_value.GetUniqueId.return_value = 'new'
        with self.assertRaisesRegex(RuntimeError, 'Project changed'):
            app.request({'command': 'relink', 'key': '0', 'target': 'x'})


if __name__ == '__main__':
    unittest.main()
