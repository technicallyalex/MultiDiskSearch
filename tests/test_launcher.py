import sys
import types
import unittest
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
from unittest.mock import Mock, patch


class LauncherTests(unittest.TestCase):
    def test_resolve_exec_without_file_or_name_uses_embedded_path(self):
        directory = str(PROJECT_ROOT)
        source = (Path(directory) / 'MultiDiskSearch.py').read_text(encoding='utf-8')
        source = source.replace('INSTALL_DIRECTORY = None  # Set by installer.', 'INSTALL_DIRECTORY = ' + repr(directory))
        resolve = object()
        core = types.ModuleType('relink_core')
        core.connect = Mock(side_effect=AssertionError('Must use injected Resolve'))
        bridge = types.ModuleType('resolve_bridge')
        bridge.serve = Mock()
        namespace = {'resolve': resolve}
        with patch.dict(sys.modules, relink_core=core, resolve_bridge=bridge):
            exec(compile(source, '<Resolve integration>', 'exec'), namespace)
        bridge.serve.assert_called_once_with(resolve, directory)
        self.assertNotIn('__file__', namespace)

    def test_direct_source_launch_locates_application_files(self):
        import MultiDiskSearch
        self.assertEqual(Path(MultiDiskSearch.application_directory()), PROJECT_ROOT)


if __name__ == '__main__':
    unittest.main()
