import hashlib
import io
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from app_update import RELEASES_URL, download_installer, installer_asset


class AppUpdateTests(unittest.TestCase):
    def test_only_exact_verified_release_installer_is_accepted(self):
        name = 'MultiDiskSearch-1.2.0-Setup.exe'
        url = f'{RELEASES_URL}/download/v1.2.0/{name}'
        digest = 'a' * 64
        asset = {'name': name, 'state': 'uploaded', 'size': 500,
                 'browser_download_url': url, 'digest': 'sha256:' + digest}
        self.assertEqual(installer_asset({'tag_name': 'v1.2.0', 'assets': [asset]}), (name, url, digest, 500))
        for override in ({'digest': None}, {'browser_download_url': 'https://example.org/Setup.exe'},
                         {'size': 0}, {'state': 'new'}):
            self.assertIsNone(installer_asset({'tag_name': 'v1.2.0', 'assets': [dict(asset, **override)]}))

    def test_download_keeps_verified_installer_and_removes_invalid_files(self):
        blob = b'installer fixture'
        url = 'https://github.com/technicallyalex/MultiDiskSearch/releases/download/v1.2.0/setup.exe'

        class Response(io.BytesIO):
            def geturl(self):
                return url

        with tempfile.TemporaryDirectory() as temp:
            valid = Path(temp) / 'valid'
            invalid = Path(temp) / 'invalid'
            valid.mkdir()
            invalid.mkdir()
            with patch('app_update.tempfile.mkdtemp', return_value=str(valid)), patch('app_update.urlopen', return_value=Response(blob)):
                result = download_installer(('setup.exe', url, hashlib.sha256(blob).hexdigest(), len(blob)),
                                            threading.Event(), lambda *_: None)
                self.assertEqual(result.read_bytes(), blob)
            with patch('app_update.tempfile.mkdtemp', return_value=str(invalid)), patch('app_update.urlopen', return_value=Response(blob)):
                with self.assertRaisesRegex(ValueError, 'checksum'):
                    download_installer(('setup.exe', url, '0' * 64, len(blob)), threading.Event(), lambda *_: None)
                self.assertFalse(invalid.exists())
