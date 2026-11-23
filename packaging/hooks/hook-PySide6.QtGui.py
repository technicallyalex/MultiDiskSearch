"""Keep GUI plugins required by the app, excluding unrelated optional modules."""
from pathlib import Path
from PyInstaller.utils.hooks.qt import add_qt6_dependencies

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
binaries = [(source, destination) for source, destination in binaries
            if Path(source).name.lower() not in {'qtvirtualkeyboardplugin.dll', 'qpdf.dll'}]
