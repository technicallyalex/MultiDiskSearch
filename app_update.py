"""Validate, download, and hand off a published Windows update."""
import ctypes
import hashlib
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from urllib.request import urlopen


RELEASES_URL = 'https://github.com/technicallyalex/MultiDiskSearch/releases'


def installer_asset(release):
    tag = release['tag_name']
    name = f'MultiDiskSearch-{tag.removeprefix("v")}-Setup.exe'
    url = f'{RELEASES_URL}/download/{tag}/{name}'
    for asset in release.get('assets', []):
        digest, size = asset.get('digest'), asset.get('size')
        if (asset.get('name') == name and asset.get('state') == 'uploaded'
                and asset.get('browser_download_url') == url and isinstance(digest, str)
                and re.fullmatch(r'sha256:[a-fA-F0-9]{64}', digest)
                and type(size) is int and 0 < size <= 256 * 1024**2):
            return name, url, digest[7:].lower(), size
    return None


def installed_app():
    if sys.platform != 'win32' or not getattr(sys, 'frozen', False):
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'Software\MultiDiskSearch',
                            access=winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            directory = winreg.QueryValueEx(key, 'InstallDir')[0]
        return Path(sys.executable).resolve() == (Path(directory) / 'MultiDiskSearch.exe').resolve()
    except OSError:
        return False


def download_installer(asset, cancelled, progress):
    name, url, expected, size = asset
    folder = Path(tempfile.mkdtemp(prefix='MultiDiskSearch-update-'))
    path = folder / name
    digest = hashlib.sha256()
    downloaded = 0
    deadline = time.monotonic() + 300
    try:
        with urlopen(url, timeout=15) as response, path.open('xb') as output:
            if not response.geturl().startswith('https://'):
                raise ValueError('The installer download did not use HTTPS.')
            while chunk := response.read(128 * 1024):
                if cancelled.is_set() or time.monotonic() > deadline:
                    raise TimeoutError('Installer download stopped or timed out.')
                downloaded += len(chunk)
                if downloaded > size:
                    raise ValueError('The installer size does not match the release.')
                digest.update(chunk)
                output.write(chunk)
                progress(downloaded, size)
        if downloaded != size or digest.hexdigest() != expected:
            raise ValueError('The installer checksum does not match the release.')
        return path
    except Exception:
        path.unlink(missing_ok=True)
        folder.rmdir()
        raise


def run_installer(path):
    """Ask Windows to elevate. The installer waits for this process to exit."""
    from ctypes import wintypes
    shell_execute = ctypes.windll.shell32.ShellExecuteW
    shell_execute.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR,
                              wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_int]
    shell_execute.restype = ctypes.c_ssize_t
    return shell_execute(None, 'runas', str(path), f'/S /UPDATEPID={os.getpid()}', str(path.parent), 0) > 32


def discard_installer(path):
    path.unlink(missing_ok=True)
    path.parent.rmdir()
