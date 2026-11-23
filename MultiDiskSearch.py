"""Installed into Resolve's Workflow Integration Plugins directory."""
import ctypes
import json
from pathlib import Path
import sys

INSTALL_DIRECTORY = None  # Set by installer.


def application_directory():
    # Resolve may exec integration scripts without setting __file__.
    if INSTALL_DIRECTORY:
        directory = Path(INSTALL_DIRECTORY)
    else:
        script_path = globals().get('__file__')
        if not script_path:
            raise RuntimeError('Application location missing. Run Install.ps1 again.')
        config = Path(script_path).with_suffix('.json')
        directory = Path(json.loads(config.read_text(encoding='utf-8-sig'))['directory']) if config.exists() else Path(script_path).parent
    if not (directory / 'resolve_bridge.py').is_file() or not (directory / 'qt_app.py').is_file():
        raise RuntimeError('Application files are missing. Reinstall Multi Disk Search from its application folder.')
    return str(directory)


def main():
    try:
        directory = application_directory()
        sys.path.insert(0, directory)
        from relink_core import connect
        from resolve_bridge import serve
        resolve = globals().get('resolve') or connect()
        if not resolve:
            raise RuntimeError('Resolve is unavailable. Open a project first.')
        serve(resolve, directory)
    except Exception as error:
        ctypes.windll.user32.MessageBoxW(0, str(error), 'Multi Disk Search', 16)


if globals().get('resolve') is not None or globals().get('__name__') == '__main__':
    main()
